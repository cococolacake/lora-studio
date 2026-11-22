"""Dataset folder tools that don't need torch: captions, bulk tag edits (with undo), rename,
delete/restore, crop & resize, tag autocomplete."""
import csv
import os
import shutil
import threading
from pathlib import Path

from PIL import Image, ImageOps

from .util import Task, is_image, natural_key

DUPES, DELETED, ORIGINALS = "_duplicates", "_deleted", "_originals"
METADATA = "_metadata"          # gallery-dl's per-image .json files (tags for captions)
BINS = {DUPES, DELETED, ORIGINALS}
SPECIAL_DIRS = BINS | {METADATA}  # folders that scans and imports skip


def tag_key(tag):
    return " ".join(tag.strip().lower().replace("_", " ").split())


def parse_tags(text):
    return [t.strip() for t in (text or "").replace("\n", ",").split(",") if t.strip()]


def join_tags(tags):
    return ", ".join(tags)


def cap_path(img, ext=".txt"):
    return str(Path(img).with_suffix(ext))


def _read(p):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _write(p, text):
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def unique_dest(folder, name):
    dest = Path(folder) / name
    stem, suf, n = dest.stem, dest.suffix, 1
    while dest.exists():
        dest = Path(folder) / f"{stem}_{n}{suf}"
        n += 1
    return dest


# ---- listing --------------------------------------------------------------

def list_folder(folder, ext=".txt", sub=None):
    """Images in a folder with their captions. sub='_deleted' lists that bin instead."""
    base = Path(folder)
    d = base / sub if sub else base
    if not d.is_dir():
        raise RuntimeError(f"Folder not found: {d}")
    out = []
    for f in sorted([f for f in d.iterdir() if f.is_file() and is_image(f.name)], key=lambda f: natural_key(f.name)):
        w = h = None
        try:
            with Image.open(f) as im:
                w, h = im.size
        except Exception:
            pass
        text = _read(cap_path(f, ext))
        out.append({"path": str(f).replace("\\", "/"), "name": f.name, "w": w, "h": h,
                    "caption": text if text is not None else None,
                    "backup": (base / ORIGINALS / f.name).exists()})
    bins = {s: sum(1 for x in (base / s).iterdir() if is_image(x.name)) if (base / s).is_dir() else 0
            for s in (DELETED, DUPES)}
    return {"folder": str(base).replace("\\", "/"), "images": out, "bins": bins}


def save_caption(path, text, ext=".txt"):
    _write(cap_path(path, ext), (text or "").strip())
    return True


# ---- bulk edits with undo ---------------------------------------------------

_undo = {}   # folder -> [(description, {caption_path: old_text_or_None})]
_lock = threading.Lock()


def bulk(folder, op, params, paths=None, ext=".txt"):
    """op: trigger | add | delete | replace | prune. paths: limit to these images (e.g. the filtered view)."""
    imgs = paths or [i["path"] for i in list_folder(folder, ext)["images"]]
    tags = parse_tags(params.get("tags", ""))
    if op == "trigger":
        trig = (params.get("trigger") or "").strip()
        if not trig:
            raise RuntimeError("Enter a trigger word first.")
        k = tag_key(trig)
        fn, create, desc = (lambda ts: [trig] + [t for t in ts if tag_key(t) != k]), True, f"Add trigger “{trig}”"
    elif op == "add":
        def fn(ts):
            keys = {tag_key(t) for t in ts}
            return ts + [t for t in tags if tag_key(t) not in keys]
        create, desc = True, f"Add {', '.join(tags)}"
    elif op == "delete":
        targets = {tag_key(t) for t in tags}
        fn, create, desc = (lambda ts: [t for t in ts if tag_key(t) not in targets]), False, f"Delete {', '.join(tags)}"
    elif op == "prune":
        # character LoRA clean-up: drop the tags the trigger should absorb, and put the trigger
        # first, in one step so a single undo brings everything back
        targets = {tag_key(t) for t in tags}
        trig = (params.get("trigger") or "").strip()
        tk = tag_key(trig) if trig else None
        targets.discard(tk)

        def fn(ts):
            kept = [t for t in ts if tag_key(t) not in targets and tag_key(t) != tk]
            return [trig] + kept if trig else kept
        create = False
        desc = f"Remove {len(targets)} character tag{'' if len(targets) == 1 else 's'}" + (f", “{trig}” first" if trig else "")
    elif op == "replace":
        dst = (params.get("replace_with") or "").strip()
        if not dst:
            raise RuntimeError("Enter the replacement tag.")
        srcs, dk = {tag_key(t) for t in tags}, tag_key(dst)

        def fn(ts):
            keys = [tag_key(t) for t in ts]
            if not any(k in srcs for k in keys):
                return ts
            have = dk in keys and dk not in srcs
            out = []
            for t, k in zip(ts, keys):
                if k in srcs:
                    if not have:
                        out.append(dst)
                        have = True
                else:
                    out.append(t)
            return out
        create, desc = False, f"Replace {', '.join(tags)} → {dst}"
    else:
        raise RuntimeError(f"Unknown operation {op}")
    if op != "trigger" and not tags:
        raise RuntimeError("Enter one or more tags (comma separated).")

    snapshot, changed = {}, 0
    for img in imgs:
        cp = cap_path(img, ext)
        old = _read(cp)
        if old is None and not create:
            continue
        new = join_tags(fn(parse_tags(old or "")))
        if new != (old or "").strip() or old is None:
            snapshot[cp] = old
            _write(cp, new)
            changed += 1
    if snapshot:
        with _lock:
            _undo.setdefault(folder, []).append((desc, snapshot))
            _undo[folder] = _undo[folder][-20:]
    return {"changed": changed, "description": desc, "can_undo": bool(_undo.get(folder))}


def undo(folder):
    with _lock:
        stack = _undo.get(folder) or []
        if not stack:
            raise RuntimeError("Nothing to undo.")
        desc, snap = stack.pop()
    for cp, old in snap.items():
        if old is None:
            Path(cp).unlink(missing_ok=True)
        else:
            _write(cp, old)
    return {"description": desc, "restored": len(snap), "can_undo": bool(_undo.get(folder))}


def can_undo(folder):
    return bool(_undo.get(folder))


# ---- delete / restore / move -------------------------------------------------

def move_images(paths, to_sub, ext=".txt"):
    """Move images (and their captions) into <their folder>/<to_sub>/."""
    n, dests = 0, []
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        dest_dir = p.parent / to_sub
        dest_dir.mkdir(exist_ok=True)
        dest = unique_dest(dest_dir, p.name)
        shutil.move(str(p), str(dest))
        cap = Path(cap_path(p, ext))
        if cap.exists():
            shutil.move(str(cap), str(dest.with_suffix(ext)))
        n += 1
        dests.append(str(dest).replace("\\", "/"))
    return {"moved": n, "dest": dests}


def restore_images(paths, ext=".txt"):
    """Move images out of a _deleted/_duplicates bin back to the dataset folder."""
    n = 0
    for p in paths:
        p = Path(p)
        if not p.exists() or p.parent.name not in BINS:
            continue
        target = unique_dest(p.parent.parent, p.name)
        shutil.move(str(p), str(target))
        cap = Path(cap_path(p, ext))
        if cap.exists():
            shutil.move(str(cap), str(target.with_suffix(ext)))
        n += 1
    return n


def empty_bin(folder, which):
    """Permanently delete <folder>/_duplicates or <folder>/_deleted (after you've reviewed it)."""
    if which not in (DUPES, DELETED):
        raise RuntimeError("Only _duplicates and _deleted can be emptied.")
    d = Path(folder) / which
    if not d.is_dir():
        return {"deleted": 0}
    n = sum(1 for f in d.iterdir() if is_image(f.name))
    shutil.rmtree(d)
    return {"deleted": n}


def bin_info(folder):
    out = {}
    for b in (DUPES, DELETED):
        d = Path(folder) / b
        out[b] = sum(1 for f in d.iterdir() if is_image(f.name)) if d.is_dir() else 0
    return out


# ---- rename (two-phase, never overwrites) -------------------------------------

def rename_plan(folder, prefix="DATA_", start=1, recursive=False, ext=".txt"):
    plans = []
    for cur, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SPECIAL_DIRS]
        cur = Path(cur)
        imgs = sorted([cur / f for f in files if is_image(f)], key=natural_key)
        if imgs:
            moving, plan, conflicts = set(), [], []
            for i, p in enumerate(imgs, start=start):
                cap = Path(cap_path(p, ext))
                cap = cap if cap.exists() else None
                moving.add(p)
                if cap:
                    moving.add(cap)
                plan.append({"from": str(p), "to": str(cur / f"{prefix}{i}{p.suffix.lower()}"),
                             "cap_from": str(cap) if cap else None,
                             "cap_to": str(cur / f"{prefix}{i}{ext}") if cap else None})
            for item in plan:
                for t in (item["to"], item["cap_to"]):
                    if t and Path(t).exists() and Path(t) not in moving:
                        conflicts.append(Path(t).name)
            plans.append({"folder": str(cur), "items": plan, "conflicts": conflicts})
        if not recursive:
            break
    return plans


def rename_apply(folder, prefix="DATA_", start=1, recursive=False, ext=".txt"):
    done, skipped = 0, []
    for fp in rename_plan(folder, prefix, start, recursive, ext):
        if fp["conflicts"]:
            skipped.append(fp["folder"])
            continue
        staged = []
        for n, it in enumerate(fp["items"]):
            src = Path(it["from"])
            tmp = src.with_name(f"__renaming_{n}{src.suffix.lower()}")
            src.rename(tmp)
            tcap = None
            if it["cap_from"]:
                tcap = src.with_name(f"__renaming_{n}{ext}")
                Path(it["cap_from"]).rename(tcap)
            staged.append((tmp, tcap, it))
        for tmp, tcap, it in staged:
            tmp.rename(it["to"])
            if tcap:
                tcap.rename(it["cap_to"])
            done += 1
    return {"renamed": done, "skipped_folders": skipped}


# ---- crop & resize -----------------------------------------------------------

def _backup(path):
    p = Path(path)
    bdir = p.parent / ORIGINALS
    bdir.mkdir(exist_ok=True)
    b = bdir / p.name
    if not b.exists():           # keep the very first original
        shutil.copy2(p, b)


def _save_like(im, path):
    p = Path(path)
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".bmp": "BMP"}.get(p.suffix.lower(), "PNG")
    if fmt == "JPEG" and im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    kw = {"quality": 95} if fmt in ("JPEG", "WEBP") else {}
    im.save(p, fmt, **kw)


def crop_image(path, box, out_w=None, out_h=None):
    """box = [x, y, w, h] in original pixels. Optionally resize the crop to out_w × out_h."""
    _backup(path)
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        x, y, w, h = [int(round(v)) for v in box]
        x, y = max(0, x), max(0, y)
        w, h = min(w, im.width - x), min(h, im.height - y)
        out = im.crop((x, y, x + w, y + h))
        if out_w and out_h:
            out = out.resize((int(out_w), int(out_h)), Image.Resampling.LANCZOS)
        out.load()
    _save_like(out, path)
    return {"w": out.width, "h": out.height}


def restore_original(path):
    p = Path(path)
    b = p.parent / ORIGINALS / p.name
    if not b.exists():
        raise RuntimeError("No backup of this image.")
    shutil.copy2(b, p)
    b.unlink()
    return True


def _fit(im, mode, w, h, anchor, upscale):
    W, H = im.size
    if mode == "long":
        s = w / max(W, H)
    elif mode == "short":
        s = w / min(W, H)
    else:  # exact: scale to cover, then crop
        s = max(w / W, h / H)
    if s > 1 and not upscale and mode != "exact":
        return None
    if mode in ("long", "short"):
        return im.resize((max(1, round(W * s)), max(1, round(H * s))), Image.Resampling.LANCZOS)
    rs = im.resize((max(w, round(W * s)), max(h, round(H * s))), Image.Resampling.LANCZOS)
    left = (rs.width - w) // 2
    top = 0 if anchor == "top" else (rs.height - h) // 2
    return rs.crop((left, top, left + w, top + h))


def batch_resize(task, folder, mode, width, height=None, anchor="center", upscale=False, paths=None):
    """mode: long (long side = width) | short (short side = width) | exact (crop to width×height)."""
    imgs = paths or [i["path"] for i in list_folder(folder)["images"]]
    total, changed = len(imgs), 0
    for n, p in enumerate(imgs, 1):
        try:
            with Image.open(p) as im:
                im = ImageOps.exif_transpose(im)
                out = _fit(im, mode, int(width), int(height or width), anchor, upscale)
                if out is not None and out.size != im.size:
                    out.load()
                else:
                    out = None
            if out is not None:
                _backup(p)
                _save_like(out, p)
                changed += 1
        except Exception as e:
            task.log(f"{Path(p).name}: {e}")
        task.progress = {"n": n, "total": total, "msg": f"{n}/{total}"}
    task.log(f"Resized {changed} of {total} images. Originals are in {ORIGINALS}/.")
    return {"changed": changed, "total": total}


def start_batch_resize(**kw):
    return Task.spawn("Resizing images", batch_resize, *[kw.get(k) for k in
                      ("folder", "mode", "width", "height", "anchor", "upscale", "paths")])


# ---- autocomplete ------------------------------------------------------------

_ac = {"path": None, "tags": [], "lower": [], "cat": {}}


def _load_ac(csv_path):
    if _ac["path"] == csv_path:
        return
    tags, cat = [], {}
    if csv_path and os.path.exists(csv_path):
        csv.field_size_limit(10_000_000)
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            for row in csv.reader(f):
                if row and row[0].strip():
                    tags.append(row[0].strip().replace("_", " "))
                    # danbooru-style csvs: tag,category,count,aliases (category 4 = character)
                    if len(row) > 1 and row[1].strip().isdigit():
                        cat[tag_key(row[0])] = int(row[1])
    _ac.update(path=csv_path, tags=tags, lower=[t.lower() for t in tags], cat=cat)


def tag_category(csv_path, tag):
    """Danbooru category number of a tag from the autocomplete csv (4 = character), or None."""
    _load_ac(csv_path)
    return _ac["cat"].get(tag_key(tag))


def autocomplete(csv_path, prefix, limit=12):
    _load_ac(csv_path)
    q = prefix.strip().lower().replace("_", " ")
    if not q:
        return []
    starts, contains = [], []
    for t, low in zip(_ac["tags"], _ac["lower"]):
        if low.startswith(q):
            starts.append(t)
            if len(starts) >= limit:
                break
        elif len(contains) < limit and q in low:
            contains.append(t)
    return (starts + contains)[:limit]


def find_autocomplete_csvs(swarm_dir):
    d = Path(swarm_dir or "") / "Data" / "Autocompletions"
    return sorted(str(f).replace("\\", "/") for f in d.glob("*.csv")) if swarm_dir and d.is_dir() else []


# ---- character tags ----------------------------------------------------------
# For a character LoRA trained on one trigger word, tags that describe the character's fixed
# look (hair, eyes, body features, default outfit) should be removed so the trigger learns
# them. Tags that change between images (pose, expression, framing, background, held objects)
# must stay. These word lists sort danbooru-style tags into those groups.

_HAIR = ("hair", "bangs", "sidelocks", "ahoge", "ponytail", "twintails", "braid", "braids", "bun",
         "drill", "drills", "hime cut", "bob cut", "pixie cut", "two side up", "one side up",
         "hair intakes", "antenna hair", "bald", "undercut", "mohawk", "afro", "dreadlocks")
_HAIR_ACCESSORY = ("hair ornament", "hair ribbon", "hair bow", "hair flower", "hairclip", "hairband",
                   "hair bobbles", "hairpin", "hair tie", "hair scrunchie", "hair stick", "hair bun cover")
_EYES = ("eyes", "pupils", "heterochromia", "eyelashes", "sclera", "tsurime", "tareme", "eyeshadow", "eyeliner")
_BODY = ("skin", "ears", "tail", "horns", "horn", "wings", "halo", "fangs", "fang", "mole", "freckles",
         "scar", "tattoo", "breasts", "flat chest", "muscular", "abs", "elf", "pointy ears", "facial mark",
         "whisker markings", "makeup", "lipstick", "nail polish", "dark-skinned", "toned", "petite",
         "mature female", "aged down", "tall female", "animal ear fluff", "third eye", "body markings")
_OUTFIT = ("dress", "shirt", "skirt", "jacket", "coat", "hoodie", "sweater", "cardigan", "vest", "uniform",
           "serafuku", "kimono", "yukata", "hakama", "gloves", "glove", "thighhighs", "thighhigh", "pantyhose",
           "socks", "kneehighs", "legwear", "boots", "shoes", "sandals", "heels", "loafers", "sneakers",
           "shorts", "pants", "jeans", "leotard", "bodysuit", "swimsuit", "bikini", "apron", "cape", "cloak",
           "robe", "scarf", "necktie", "tie", "bowtie", "ribbon", "ribbons", "bow", "collar", "choker",
           "belt", "sleeves", "sleeve", "sleeveless", "strapless", "off shoulder", "bare shoulders",
           "cutout", "frills", "frilled", "buttons", "zipper", "armor", "armlet", "hat", "beret", "cap",
           "hood", "headband", "headwear", "headgear", "earrings", "earring", "necklace", "jewelry",
           "bracelet", "bracelets", "wristband", "glasses", "eyewear", "goggles", "headphones", "crown",
           "tiara", "veil", "garter", "garters", "lingerie", "bra", "corset", "neckerchief", "sailor collar",
           "midriff", "crop top", "tank top", "camisole", "blouse", "suit", "tuxedo", "overalls", "maid",
           "nun", "habit", "witch", "pendant", "brooch", "gem", "wrist cuffs", "arm warmers",
           "leg warmers", "detached collar", "pelvic curtain", "obi", "sash", "harness", "epaulettes",
           "aiguillette", "shoulder armor", "gauntlets", "greaves", "clothes", "clothing", "outfit",
           "costume", "leggings", "stockings", "tights", "tabard", "poncho", "parka", "blazer",
           "turtleneck", "hairband", "kneepits") + _HAIR_ACCESSORY

# tags that mention a feature but describe something that changes per image
_VARIABLE = ("holding", "hand in", "hand on", "hands on", "adjusting", "playing with", "touching",
             "tucking", "pulling", "lift", "lifted", "lifting", "tug", "grab", "grabbing", "removing",
             "taking off", "unworn", "no ", "wet", "blowing", "floating", "flowing", "messy", "covering",
             "closed eyes", "half-closed eyes", "one eye closed", "eyes visible", "wide-eyed", "rolling eyes",
             "empty eyes", "crazy eyes", "glowing", "looking", "open clothes", "open jacket", "open shirt",
             "open coat", "undressing", "torn", "wardrobe", "partially", "clothes down", "on head",
             "on lap", "between", "in mouth", "biting", "licking", "spread", "showing", "lowered",
             "upskirt", "pantyshot", "cleavage", "sideboob", "underboob", "see-through", "steam",
             "sweat", "blush", "tears", "drool", "nude", "naked", "topless", "bottomless", "breast press",
             "breast hold", "breast grab", "hug", "wagging", "raised", "crossed", "own hands", "shadow",
             "silhouette", "multiple girls", "multiple boys", "other", "background", "artist",
             "signature", "watermark", "username", "web address", "text")


# fixed features that would otherwise trip a _VARIABLE word
_FIXED = {"hair between eyes": "hair", "hair over one eye": "hair", "hair over eyes": "hair",
          "crossed bangs": "hair", "multicolored eyes": "eyes"}


def _has_phrase(key, phrases):
    padded = f" {key} "
    return any(f" {p} " in padded or (p.endswith("-") and f" {p}" in padded) for p in phrases)


def classify_tag(tag):
    """'hair' | 'eyes' | 'body' | 'outfit' for a tag describing the character's fixed look, else None."""
    k = tag_key(tag)
    if k in _FIXED:
        return _FIXED[k]
    padded = f" {k} "
    if any(f" {v.strip()} " in padded if not v.endswith(" ") else padded.startswith(f" {v}") for v in _VARIABLE):
        return None
    if _has_phrase(k, _HAIR_ACCESSORY):
        return "outfit"
    if _has_phrase(k, _HAIR):
        return "hair"
    if _has_phrase(k, _EYES):
        return "eyes"
    if _has_phrase(k, _BODY):
        return "body"
    if _has_phrase(k, _OUTFIT):
        return "outfit"
    return None


def character_tags(folder, trigger="", paths=None, csv_path=None, ext=".txt"):
    """Tags in a dataset that describe the character's fixed look, with how many captions use them.
    Returns {"total": n_captions, "tags": [{tag, count, group}]}, groups: name/hair/eyes/body/outfit."""
    imgs = paths or [i["path"] for i in list_folder(folder, ext)["images"]]
    tk = tag_key(trigger) if trigger else None
    counts, spelling, total = {}, {}, 0
    for img in imgs:
        text = _read(cap_path(img, ext))
        if text is None:
            continue
        total += 1
        for t in parse_tags(text):
            spelling.setdefault(tag_key(t), t)      # show the tag as it's written in the captions
        for k in {tag_key(t) for t in parse_tags(text)} - {tk}:
            counts[k] = counts.get(k, 0) + 1
    out = []
    for k, n in counts.items():
        group = "name" if csv_path and tag_category(csv_path, k) == 4 else classify_tag(k)
        if group:
            out.append({"tag": spelling.get(k, k), "count": n, "group": group})
    out.sort(key=lambda x: (-x["count"], tag_key(x["tag"])))
    return {"total": total, "tags": out}
