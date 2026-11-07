"""Turn a downloaded folder (e.g. from gallery-dl) into a clean dataset in one go:
copy images, skip tiny ones, number them, and write captions from the download's tags."""
import json
import shutil
from pathlib import Path

from PIL import Image

from .dataset_tools import METADATA, SPECIAL_DIRS, tag_key
from .util import is_image, natural_key


def _tags_from_metadata(img, opts):
    """Danbooru-style tags from gallery-dl's metadata (file.jpg.json) or tag files (file.jpg.txt)."""
    img = Path(img)
    for js in (img.parent / METADATA / (img.name + ".json"), img.with_name(img.name + ".json"), img.with_suffix(".json")):
        if js.exists():
            try:
                data = json.loads(js.read_text(encoding="utf-8", errors="replace"))
            except ValueError:
                continue
            groups = []
            if "tag_string_general" in data:
                if opts.get("character", True):
                    groups.append(data.get("tag_string_character", ""))
                if opts.get("copyright"):
                    groups.append(data.get("tag_string_copyright", ""))
                if opts.get("artist"):
                    groups.append(data.get("tag_string_artist", ""))
                groups.append(data.get("tag_string_general", ""))
                tags = " ".join(groups).split()
            elif isinstance(data.get("tags"), list):
                tags = [t.get("name", "") if isinstance(t, dict) else str(t) for t in data["tags"]]
            elif isinstance(data.get("tags"), str):
                tags = data["tags"].split()
            elif isinstance(data.get("tag_string"), str):
                tags = data["tag_string"].split()
            else:
                continue
            return [t.replace("_", " ").strip() for t in tags if t.strip()]
    for txt in (img.with_name(img.name + ".txt"),):
        if txt.exists():   # gallery-dl's "tags" post-processor: one tag per line
            lines = txt.read_text(encoding="utf-8", errors="replace").splitlines()
            return [l.replace("_", " ").strip() for l in lines if l.strip()]
    return None


def run(task, p):
    src, dest = Path(p["source"]), Path(p["dest"])
    if not src.is_dir():
        raise RuntimeError(f"Source folder not found: {src}")
    if dest.resolve() == src.resolve():
        return _in_place(task, src, p)   # e.g. "Download into" and "Save the dataset in" are the same folder
    if dest.exists() and any(is_image(f.name) for f in dest.iterdir()):
        raise RuntimeError("The destination already has images in it. Pick a new or empty folder, "
                           "or the same folder the images are in to build the dataset right there.")
    dest.mkdir(parents=True, exist_ok=True)
    images = _only(p, [])
    if images is None:
        images = []
        for f in sorted(src.rglob("*") if p.get("recursive", True) else src.iterdir(), key=lambda f: natural_key(str(f))):
            if f.is_file() and is_image(f.name) and not (set(f.relative_to(src).parts[:-1]) & SPECIAL_DIRS):
                images.append(f)
    min_side = int(p.get("min_side") or 0)
    prefix = p.get("prefix", "DATA_")
    trigger = (p.get("trigger") or "").strip()
    use_meta = p.get("captions", "metadata") == "metadata"
    n = int(p.get("start") or 1)
    stats = {"found": len(images), "copied": 0, "too_small": 0, "unreadable": 0, "captioned": 0, "uncaptioned": 0}
    for i, f in enumerate(images, 1):
        task.progress = {"n": i, "total": len(images), "msg": f"Copying {i}/{len(images)}"}
        try:
            with Image.open(f) as im:
                w, h = im.size
        except Exception:
            stats["unreadable"] += 1
            continue
        if min_side and min(w, h) < min_side:
            stats["too_small"] += 1
            continue
        target = dest / f"{prefix}{n}{f.suffix.lower()}"
        shutil.copy2(f, target)
        tags = _tags_from_metadata(f, p) if use_meta else None
        if tags is None and not use_meta:
            existing = f.with_suffix(".txt")   # keep captions that were already made for these images
            if existing.exists():
                tags = [t.strip() for t in existing.read_text(encoding="utf-8", errors="replace").split(",") if t.strip()]
        if trigger:
            tags = [trigger] + [t for t in (tags or []) if tag_key(t) != tag_key(trigger)]
        if tags:
            target.with_suffix(".txt").write_text(", ".join(tags), encoding="utf-8")
            stats["captioned"] += 1
        else:
            stats["uncaptioned"] += 1
        stats["copied"] += 1
        n += 1
    task.log(f"Copied {stats['copied']} of {stats['found']} images into {dest}.")
    if stats["too_small"]:
        task.log(f"Skipped {stats['too_small']} images smaller than {min_side}px.")
    return {**stats, "dest": str(dest).replace("\\", "/")}


def _only(p, _):
    """The exact files a download just saved (or already had), if known; else None (= the whole folder)."""
    files = p.get("files")
    if files is None:
        return None
    out, seen = [], set()
    for x in files:
        f = Path(x)
        if f.is_file() and is_image(f.name) and f.resolve() not in seen:
            seen.add(f.resolve())
            out.append(f)
    return sorted(out, key=lambda f: natural_key(f.name))


def _caption_for(f, p):
    """Caption tags for one image, read before it's renamed (metadata is keyed by the original name)."""
    use_meta = p.get("captions", "metadata") == "metadata"
    tags = _tags_from_metadata(f, p) if use_meta else None
    if tags is None:
        existing = f.with_suffix(".txt")       # no site tags: keep a caption that was already made for it
        if existing.exists():
            tags = [t.strip() for t in existing.read_text(encoding="utf-8", errors="replace").split(",") if t.strip()]
    trigger = (p.get("trigger") or "").strip()
    if trigger:
        tags = [trigger] + [t for t in (tags or []) if tag_key(t) != tag_key(trigger)]
    return tags


def _in_place(task, folder, p):
    """Build the dataset inside the folder the images are already in: rename to DATA_1, DATA_2…,
    write captions, and move too-small or broken images into the _deleted bin (nothing is thrown away)."""
    from .dataset_tools import DELETED, unique_dest
    everything = sorted([f for f in folder.iterdir() if f.is_file() and is_image(f.name)], key=lambda f: natural_key(f.name))
    images = _only(p, everything)
    if images is None:
        images = everything
    else:
        others = [f for f in everything if f not in set(images)]
        if others:   # other downloads live here too: don't mix them into this dataset
            raise RuntimeError(
                f"This folder also has {len(others)} images from another download, so the dataset can't be built "
                "here without mixing them in. Your download is saved; choose a new, empty folder under "
                "'Save the dataset in' and use 'A folder on this PC' to build it from the download folder.")
    min_side = int(p.get("min_side") or 0)
    prefix = p.get("prefix", "DATA_")
    stats = {"found": len(images), "copied": 0, "too_small": 0, "unreadable": 0, "captioned": 0, "uncaptioned": 0}
    keep = []
    for i, f in enumerate(images, 1):
        task.progress = {"n": i, "total": len(images), "msg": f"Checking {i}/{len(images)}"}
        try:
            with Image.open(f) as im:
                w, h = im.size
        except Exception:
            w = h = None
        if w is None or (min_side and min(w, h) < min_side):
            stats["unreadable" if w is None else "too_small"] += 1
            bin_dir = folder / DELETED
            bin_dir.mkdir(exist_ok=True)
            shutil.move(str(f), str(unique_dest(bin_dir, f.name)))
            old_txt = f.with_suffix(".txt")
            if old_txt.exists():
                shutil.move(str(old_txt), str(unique_dest(bin_dir, old_txt.name)))
            continue
        keep.append((f, _caption_for(f, p)))
    # Rename in two steps (to temporary names first), so no file can overwrite another.
    temps = []
    for k, (f, tags) in enumerate(keep):
        old_txt = f.with_suffix(".txt")
        if old_txt.exists():
            old_txt.unlink()                  # replaced by the new caption below
        tmp = folder / f".lstmp_{k}{f.suffix.lower()}"
        f.rename(tmp)
        temps.append((tmp, tags))
    n = int(p.get("start") or 1)
    for tmp, tags in temps:
        target = folder / f"{prefix}{n}{tmp.suffix}"
        if target.exists():
            target = unique_dest(folder, target.name)
        tmp.rename(target)
        if tags:
            target.with_suffix(".txt").write_text(", ".join(tags), encoding="utf-8")
            stats["captioned"] += 1
        else:
            stats["uncaptioned"] += 1
        stats["copied"] += 1
        n += 1
    task.log(f"Built the dataset in place: {stats['copied']} of {stats['found']} images in {folder}.")
    if stats["too_small"] or stats["unreadable"]:
        task.log(f"Moved {stats['too_small'] + stats['unreadable']} too-small or unreadable images into the {DELETED} bin.")
    return {**stats, "dest": str(folder).replace("\\", "/")}


def make_dataset(task, p):
    """The one-button flow: (optionally) download with gallery-dl, then import into a clean dataset."""
    from . import gallerydl
    src = p.get("source")
    files = None
    if p.get("url"):
        dl, dest = Path(p["download_dir"]), Path(p["dest"])
        if dl.exists() and dest.exists() and dl.resolve() == dest.resolve():
            if any(f.is_file() and is_image(f.name) and f.stem.startswith(p.get("prefix", "DATA_")) for f in dl.iterdir()):
                raise RuntimeError("That folder already has a finished dataset in it. Choose a new, empty folder "
                                   "for this download so the two don't get mixed.")
        task.log(f"Downloading {p['url']}")
        res = gallerydl.download(task, p["url"], p["download_dir"], p.get("limit"))
        src, files = res["dest"], res["files"]
    if not src:
        raise RuntimeError("Choose a folder to import, or something to download.")
    task.log("\nBuilding the dataset…")
    out = run(task, {**p, "source": src, "files": files})
    out["source"] = src
    return out
