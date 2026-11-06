"""Read and edit the metadata inside .safetensors LoRA files (no torch needed).

SwarmUI shows the modelspec.* fields (title, description, trigger phrase, thumbnail) in its model browser.
"""
import base64
import io
import json
import os
import struct
from pathlib import Path

EDITABLE = ["modelspec.title", "modelspec.description", "modelspec.author", "modelspec.trigger_phrase",
            "modelspec.tags", "modelspec.usage_hint", "modelspec.thumbnail"]


def read_header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        if n > 100_000_000:
            raise RuntimeError("That doesn't look like a .safetensors file.")
        return json.loads(f.read(n)), 8 + n


def read(path):
    header, _ = read_header(path)
    meta = header.get("__metadata__") or {}
    tensors = [k for k in header if k != "__metadata__"]
    summary = {}
    for label, key in [("Base model", "ss_sd_model_name"), ("Network", "ss_network_module"), ("Rank (dim)", "ss_network_dim"),
                       ("Alpha", "ss_network_alpha"), ("Epoch", "ss_epoch"), ("Steps", "ss_steps"),
                       ("Learning rate", "ss_learning_rate"), ("Optimizer", "ss_optimizer"), ("Resolution", "ss_resolution"),
                       ("Images", "ss_num_train_images"), ("Batch size", "ss_batch_size_per_device"),
                       ("Architecture", "modelspec.architecture")]:
        if meta.get(key) not in (None, "", "None"):
            summary[label] = meta[key]
    top_tags = []
    try:
        freq = json.loads(meta.get("ss_tag_frequency") or "{}")
        counts = {}
        for d in freq.values():
            for t, n in d.items():
                counts[t.strip()] = counts.get(t.strip(), 0) + n
        top_tags = sorted(counts.items(), key=lambda kv: -kv[1])[:40]
    except (ValueError, AttributeError):
        pass
    return {"path": str(path), "name": Path(path).name, "size": os.path.getsize(path), "tensors": len(tensors),
            "editable": {k: meta.get(k, "") for k in EDITABLE}, "summary": summary, "top_tags": top_tags,
            "all": {k: (v if len(str(v)) < 400 else str(v)[:400] + "…") for k, v in sorted(meta.items())
                    if k != "modelspec.thumbnail"}}


def write(path, updates):
    """updates: {key: str or None (delete)}. Rewrites only the header; tensor data is copied as-is."""
    header, data_start = read_header(path)
    meta = dict(header.get("__metadata__") or {})
    for k, v in updates.items():
        if v is None or v == "":
            meta.pop(k, None)
        else:
            meta[k] = str(v)
    header["__metadata__"] = meta
    raw = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    raw += b" " * ((8 - len(raw) % 8) % 8)   # keep the data 8-byte aligned
    tmp = str(path) + ".lsedit"
    with open(path, "rb") as src, open(tmp, "wb") as dst:
        dst.write(struct.pack("<Q", len(raw)))
        dst.write(raw)
        src.seek(data_start)
        while True:
            chunk = src.read(16 * 1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
    os.replace(tmp, path)
    return read(path)


def thumbnail_from_image(img_path, size=256):
    from PIL import Image, ImageOps
    with Image.open(img_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def info_updates(info, thumb_path=None):
    """LoRA info from the Train form -> metadata updates."""
    up = {
        "modelspec.title": info.get("title") or None,
        "modelspec.description": info.get("description") or None,
        "modelspec.author": info.get("author") or None,
        "modelspec.trigger_phrase": info.get("trigger") or None,
        "modelspec.tags": info.get("tags") or None,
    }
    if thumb_path:
        up["modelspec.thumbnail"] = thumbnail_from_image(thumb_path)
    return {k: v for k, v in up.items() if v is not None}
