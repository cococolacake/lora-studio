import json
import os
import re
import sys

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def emit(kind, data):
    sys.stdout.write(f"@@{kind} " + json.dumps(data) + "\n")
    sys.stdout.flush()


def progress(n, total, msg=""):
    emit("P", {"n": n, "total": total, "msg": msg})


def need(*modules):
    """Import modules or report which one is missing and exit."""
    import importlib
    out = []
    for m in modules:
        try:
            out.append(importlib.import_module(m))
        except ImportError:
            pkg = {"PIL": "pillow", "huggingface_hub": "huggingface-hub"}.get(m, m)
            sys.stdout.write(f"@@MISSING {pkg}\n")
            sys.stdout.flush()
            sys.exit(3)
    return out


def load_job():
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        return json.load(f)


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def is_image(name):
    return os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS


def tag_key(tag):
    return " ".join(tag.strip().lower().replace("_", " ").split())


def parse_tags(text):
    return [t.strip() for t in text.replace("\n", ",").split(",") if t.strip()]


def device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"
