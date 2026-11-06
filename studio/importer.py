"""Turn a downloaded folder (e.g. from gallery-dl) into a clean dataset in one go:
copy images, skip tiny ones, number them, and write captions from the download's tags."""
import json
import shutil
from pathlib import Path

from PIL import Image

from .dataset_tools import SPECIAL_DIRS, tag_key
from .util import is_image, natural_key


def _tags_from_metadata(img, opts):
    """Danbooru-style tags from gallery-dl's metadata (file.jpg.json) or tag files (file.jpg.txt)."""
    img = Path(img)
    for js in (img.with_name(img.name + ".json"), img.with_suffix(".json")):
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
    if dest.exists() and any(is_image(f.name) for f in dest.iterdir()):
        raise RuntimeError("The destination already has images in it. Pick a new or empty folder.")
    if dest.resolve() == src.resolve():
        raise RuntimeError("Pick a different destination than the source.")
    dest.mkdir(parents=True, exist_ok=True)
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


def make_dataset(task, p):
    """The one-button flow: (optionally) download with gallery-dl, then import into a clean dataset."""
    from . import gallerydl
    src = p.get("source")
    if p.get("url"):
        task.log(f"Downloading {p['url']}")
        res = gallerydl.download(task, p["url"], p["download_dir"], p.get("limit"))
        src = res["dest"]
    if not src:
        raise RuntimeError("Choose a folder to import, or something to download.")
    task.log("\nBuilding the dataset…")
    out = run(task, {**p, "source": src})
    out["source"] = src
    return out
