"""Dataset health check: catch problems before a long training run does.

Also estimates buckets and steps per epoch.
"""
import math
from collections import Counter
from pathlib import Path

from PIL import Image

from .util import is_image, natural_key


def make_bucket_resolutions(max_reso, min_size, max_size, divisible):
    """Mirror of sd-scripts' make_bucket_resolutions."""
    max_w, max_h = max_reso
    max_area = max_w * max_h
    resos = set()
    width = int(math.sqrt(max_area) // divisible) * divisible
    resos.add((width, width))
    width = min_size
    while width <= max_size:
        height = min(max_size, int((max_area // width) // divisible) * divisible)
        if height >= min_size:
            resos.add((width, height))
            resos.add((height, width))
        width += divisible
    return sorted(resos)


def parse_tags(text):
    return [t.strip() for t in text.replace("\n", ",").split(",") if t.strip()]


def check(params):
    """params: {subsets:[{image_dir, num_repeats}], resolution:[w,h], enable_bucket, min_bucket_reso,
    max_bucket_reso, bucket_reso_steps, batch_size, epochs, grad_accum, caption_extension,
    trigger, min_side}"""
    ext = params.get("caption_extension") or ".txt"
    trigger = (params.get("trigger") or "").strip().lower()
    res = [int(x) for x in params.get("resolution") or [1024, 1024]]
    min_side = int(params.get("min_side") or min(res) // 2)
    bucket = bool(params.get("enable_bucket", True))
    divisible = int(params.get("bucket_reso_steps") or 64)
    resos = make_bucket_resolutions(res, int(params.get("min_bucket_reso") or 256),
                                    int(params.get("max_bucket_reso") or 2048), divisible) if bucket else [tuple(res)]
    ratios = [w / h for w, h in resos]

    issues = {k: [] for k in ("missing_caption", "empty_caption", "unreadable", "too_small",
                              "extreme_aspect", "shared_caption", "orphan_caption", "no_trigger")}
    tag_counts = Counter()
    folders = []
    total_images = 0
    total_batches = 0
    batch = max(1, int(params.get("batch_size") or 1))
    bucket_totals = Counter()

    for sub in params.get("subsets") or []:
        raw = (sub.get("image_dir") or "").strip()
        folder = Path(raw)
        if not raw or not folder.is_dir():
            folders.append({"image_dir": raw, "exists": False, "images": 0})
            continue
        repeats = max(1, int(sub.get("num_repeats") or 1))
        files = sorted([f for f in folder.iterdir() if f.is_file()], key=lambda f: natural_key(f.name))
        images = [f for f in files if is_image(f.name)]
        captions = {f.stem: f for f in files if f.suffix.lower() == ext.lower()}
        stems = Counter(f.stem for f in images)
        counts = Counter()
        for img in images:
            rel = img.name
            try:
                with Image.open(img) as im:
                    w, h = im.size
            except Exception:
                issues["unreadable"].append(_item(folder, rel))
                continue
            if min(w, h) < min_side:
                issues["too_small"].append(_item(folder, rel, f"{w}×{h}"))
            ar = w / h
            if ar > 2.5 or ar < 0.4:
                issues["extreme_aspect"].append(_item(folder, rel, f"{w}×{h}"))
            best = min(range(len(resos)), key=lambda i: abs(ratios[i] - ar))
            counts[resos[best]] += 1
            if stems[img.stem] > 1:
                issues["shared_caption"].append(_item(folder, rel, f"{img.stem}{ext} is shared"))
            cap = captions.get(img.stem)
            if not cap:
                issues["missing_caption"].append(_item(folder, rel))
                continue
            text = cap.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                issues["empty_caption"].append(_item(folder, rel))
                continue
            tags = parse_tags(text)
            tag_counts.update(t.lower() for t in tags)
            if trigger and trigger not in (t.lower() for t in tags) and trigger not in text.lower():
                issues["no_trigger"].append(_item(folder, rel))
        image_stems = set(stems)
        for stem, cap in captions.items():
            if stem not in image_stems:
                issues["orphan_caption"].append(_item(folder, cap.name))
        sub_batches = sum(math.ceil(n * repeats / batch) for n in counts.values())
        total_batches += sub_batches
        for k, v in counts.items():
            bucket_totals[k] += v
        total_images += len(images)
        folders.append({"image_dir": str(folder), "exists": True, "images": len(images),
                        "captions": len(captions), "repeats": repeats, "batches": sub_batches})

    grad = max(1, int(params.get("grad_accum") or 1))
    epochs = max(1, int(params.get("epochs") or 1))
    steps_per_epoch = math.ceil(total_batches / grad) if total_batches else 0
    severity = {"missing_caption": "warn", "empty_caption": "warn", "unreadable": "error",
                "too_small": "warn", "extreme_aspect": "info", "shared_caption": "error",
                "orphan_caption": "info", "no_trigger": "warn"}
    return {
        "folders": folders,
        "total_images": total_images,
        "issues": [{"id": k, "severity": severity[k], "count": len(v), "items": v[:200]}
                   for k, v in issues.items()],
        "top_tags": tag_counts.most_common(40),
        "unique_tags": len(tag_counts),
        "buckets": sorted([{"w": w, "h": h, "count": n} for (w, h), n in bucket_totals.items()],
                          key=lambda b: -b["count"]),
        "steps": {"batches_per_epoch": total_batches, "steps_per_epoch": steps_per_epoch,
                  "total_steps": steps_per_epoch * epochs, "epochs": epochs},
    }


def _item(folder, name, note=""):
    return {"path": str(folder / name).replace("\\", "/"), "name": name, "note": note}


def thumbnail(path, size=160):
    """Small JPEG data URL for the UI."""
    import base64
    import io
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
