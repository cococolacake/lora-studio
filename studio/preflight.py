"""The quick check before training: catches mistakes in seconds instead of after the model loads.

Looks at the settings the way sd-scripts will see them: numbers that aren't numbers, values a
setting doesn't allow, files and folders that don't exist, empty image folders, and so on.
Returns a list of {"level": "error"|"warn", "msg": ...}. Errors would make sd-scripts fail;
warnings are worth a look but training can go ahead.
"""
import re
from pathlib import Path

from . import tomlio
from .util import is_image

# Settings that point at a file or folder (same idea as the form's path fields).
PATH_KEY = re.compile(r"(_dir$|_path$|^vae$|^ae$|clip_l|clip_g|t5xxl|qwen3|gemma2|_weights$|^resume$|_file$|"
                      r"^text_encoder$|^pretrained_model_name_or_path$|^dit$|^llm$)")
MADE_FOR_YOU = {"output_dir", "logging_dir"}          # created when training starts
SAMPLE_KEYS = {"sample_prompts", "sample_every_n_epochs", "sample_every_n_steps", "sample_at_first", "sample_sampler"}
BAD_NAME = re.compile(r'[<>:"/\\|?*]')


def _looks_local(v):
    s = str(v).strip()
    return bool(s) and "://" not in s and ("/" in s or "\\" in s or re.match(r"^[A-Za-z]:", s))


def check(job):
    out = []
    err = lambda m: out.append({"level": "error", "msg": m})
    warn = lambda m: out.append({"level": "warn", "msg": m})
    args = job.get("args") or {}
    schema = {a["key"]: a for a in job.get("schema_args") or []}

    for key, raw in args.items():
        if raw is None or raw == "" or key in SAMPLE_KEYS:
            continue
        a = schema.get(key)
        if a is None:
            if schema:
                warn(f"“{key}” isn't a setting of {job.get('script') or 'this script'}; sd-scripts will ignore it or stop.")
            continue
        kind = a.get("kind", "str")
        v = tomlio.coerce(kind, raw)
        if kind in ("int", "float", "number") and isinstance(v, str):
            err(f"“{key}” should be a number, but it's “{raw}”.")
            continue
        if kind == "int" and isinstance(v, float) and not v.is_integer():
            err(f"“{key}” should be a whole number, but it's {raw}.")
        choices = a.get("choices")
        if choices and v is not None and kind != "list" and not isinstance(v, bool):
            if str(v) not in [str(c) for c in choices]:
                err(f"“{key}” can't be “{v}”. Choose one of: {', '.join(map(str, choices))}.")
        if kind == "str" and PATH_KEY.search(key) and key not in MADE_FOR_YOU and _looks_local(v):
            if not Path(str(v)).expanduser().exists():
                err(f"“{key}”: {v} wasn't found.")

    name = str(args.get("output_name") or "")
    if name and BAD_NAME.search(name):
        err(f"The output name “{name}” has characters Windows doesn't allow in file names (< > : \" / \\ | ? *).")
    out_dir = args.get("output_dir")
    if out_dir:
        parent = Path(str(out_dir)).expanduser()
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not parent.exists():
            err(f"The output folder {out_dir} can't be created (its drive or parent folder doesn't exist).")

    subsets = (job.get("dataset") or {}).get("subsets") or []
    folders = [s for s in subsets if str(s.get("image_dir") or "").strip()]
    if not folders:
        err("There's no image folder in the dataset.")
    ext = (job.get("dataset") or {}).get("caption_extension") or ".txt"
    for s in folders:
        d = Path(str(s["image_dir"])).expanduser()
        if not d.is_dir():
            err(f"Image folder {s['image_dir']} wasn't found.")
            continue
        imgs = [f for f in d.iterdir() if f.is_file() and is_image(f.name)]
        if not imgs:
            err(f"Image folder {d.name} has no images in it.")
            continue
        missing = sum(1 for f in imgs if not f.with_suffix(ext).exists())
        if missing == len(imgs):
            warn(f"None of the {len(imgs)} images in {d.name} has a caption ({ext}). Training works, but a trigger word or captions usually help.")
        elif missing:
            warn(f"{missing} of {len(imgs)} images in {d.name} have no caption ({ext}).")
    return out
