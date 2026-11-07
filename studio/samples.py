"""sd-scripts' built-in sample previews: build sample_prompts.txt, and find the images it makes."""
import re
from pathlib import Path

from .dataset_tools import parse_tags, tag_key
from .util import is_image, natural_key

DEFAULT = {
    "enabled": False,
    "every_n_epochs": 1,
    "at_first": False,
    "quality": "masterpiece, best quality",
    "quality_at": "start",
    "use_trigger": True,
    "prompts": "1girl, solo, smile, looking at viewer, upper body\n1girl, full body, standing, outdoors",
    "negative": "worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, sepia",
    "width": 1024, "height": 1024, "steps": 28, "cfg": 5, "seed": 42, "flow_shift": 3.0,
}


def _one_line(s):
    return " ".join(str(s).replace("\n", " ").split()).replace(" --", " -")


def prompt_list(cfg, trigger=""):
    """[(positive, negative)] with quality tags and trigger applied ."""
    quality = _one_line(cfg.get("quality", "")).strip(", ")
    neg = _one_line(cfg.get("negative", "")).strip(", ")
    trig = (trigger or "").strip() if cfg.get("use_trigger", True) else ""
    out = []
    for line in str(cfg.get("prompts", "")).splitlines():
        line = line.strip().strip(",").strip()
        if not line or line.startswith("#"):
            continue
        t = trig if trig and tag_key(trig) not in {tag_key(x) for x in parse_tags(line)} else ""
        parts = [t, line, quality] if cfg.get("quality_at") == "end" else [quality, t, line]
        out.append((", ".join(p for p in parts if p), neg))
    return out


def prompt_lines(cfg, trigger="", flow_shift=True):
    lines = []
    for pos, neg in prompt_list(cfg, trigger):
        line = _one_line(pos)
        if neg:
            line += f" --n {neg}"
        line += f" --w {int(cfg['width'])} --h {int(cfg['height'])} --s {int(cfg['steps'])} --l {cfg['cfg']} --d {int(cfg['seed'])}"
        if flow_shift and cfg.get("flow_shift") not in (None, ""):
            line += f" --fs {cfg['flow_shift']}"
        lines.append(line)
    return lines


# sd-scripts names samples  <output_name>_e000003_01_20250101123456_42.png  (epoch)
#                       or  <output_name>_000500_01_20250101123456_42.png   (step)
NAME_RE = re.compile(r"_(e?)(\d{6})_(\d{2})_(\d{8,14})")


def find(run):
    cfg = run.get("config") or {}
    out_dir, name = cfg.get("output_dir"), cfg.get("output_name") or ""
    d = Path(out_dir or "") / "sample"
    if not out_dir or not d.is_dir():
        return {"prompts": run.get("sample_prompts") or [], "columns": [], "cells": []}
    cells, cols = [], {}
    for f in sorted(d.iterdir(), key=lambda f: natural_key(f.name)):
        if not is_image(f.name) or (name and not f.name.startswith(name)):
            continue
        m = NAME_RE.search(f.name[len(name):] if name else f.name)
        if not m:
            continue
        is_epoch, num, idx = m.group(1) == "e", int(m.group(2)), int(m.group(3))
        col = f"{'Epoch' if is_epoch else 'Step'} {num}"
        cols[col] = (0 if is_epoch else 1, num)
        cells.append({"path": str(f).replace("\\", "/"), "name": f.name, "col": col, "row": idx,
                      "mtime": f.stat().st_mtime})
    columns = sorted(cols, key=lambda c: cols[c])
    return {"prompts": run.get("sample_prompts") or [], "columns": columns, "cells": cells}



def make_gif(run, row, ms=700, size=768):
    """An animated GIF of one prompt's samples, epoch by epoch, saved next to the samples."""
    from PIL import Image, ImageDraw, ImageFont
    grid = find(run)
    by_col = {c["col"]: c for c in grid["cells"] if c["row"] == int(row)}   # newest file per column wins
    cols = [c for c in grid["columns"] if c in by_col]
    if len(cols) < 2:
        raise RuntimeError("This prompt needs samples from at least two epochs for an animation.")
    frames = []
    for col in cols:
        with Image.open(by_col[col]["path"]) as im:
            im = im.convert("RGB")
            im.thumbnail((size, size))
            d = ImageDraw.Draw(im)
            try:
                font = ImageFont.load_default(size=max(14, im.width // 28))
            except TypeError:                      # older Pillow
                font = ImageFont.load_default()
            x0, y0, x1, y1 = d.textbbox((0, 0), col, font=font)
            pad, m = max(6, im.width // 90), max(8, im.width // 60)
            box = (m, im.height - m - (y1 - y0) - 2 * pad, m + (x1 - x0) + 2 * pad, im.height - m)
            d.rounded_rectangle(box, radius=pad * 2, fill=(255, 255, 255))
            d.text((box[0] + pad - x0, box[1] + pad - y0), col, fill=(40, 30, 50), font=font)
            frames.append(im)
    w = min(f.width for f in frames); h = min(f.height for f in frames)
    frames = [f if f.size == (w, h) else f.resize((w, h)) for f in frames]
    first = Path(by_col[cols[0]]["path"])
    name = (run.get("config") or {}).get("output_name") or "samples"
    out = first.parent / f"{name}_prompt{int(row) + 1}_epochs.gif"
    durations = [ms] * (len(frames) - 1) + [ms * 3]          # linger on the last epoch
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    return str(out).replace("\\", "/")
