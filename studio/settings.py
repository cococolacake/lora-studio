"""App settings and themes, stored as JSON in the data folder."""
import copy
import threading

from . import paths
from .util import read_json, safe_name, write_json

DEFAULT_THEME = {
    "name": "Soft Light",
    "base": "light",            # light | dark
    "accent": "periwinkle",
    "header": {
        "type": "pattern",      # pattern | image | none
        "pattern": "checker",   # see web/js/patterns.js
        "colors": ["#ECEAFF", "#FFFFFF"],
        "useAccent": True,      # derive pattern colors from the accent
        "scale": 28,
        "image": "",            # data URL when type == image
        "imageFit": "cover",    # cover | tile | contain
        "height": 132,
    },
}

BUILTIN_THEMES = [
    DEFAULT_THEME,
    {**copy.deepcopy(DEFAULT_THEME), "name": "Soft Dark", "base": "dark",
     "header": {**DEFAULT_THEME["header"], "pattern": "grid"}},
    {**copy.deepcopy(DEFAULT_THEME), "name": "Meadow", "accent": "mint",
     "header": {**DEFAULT_THEME["header"], "pattern": "sparkles"}},
    {**copy.deepcopy(DEFAULT_THEME), "name": "Peach Fuzz", "accent": "peach",
     "header": {**DEFAULT_THEME["header"], "pattern": "gingham"}},
    {**copy.deepcopy(DEFAULT_THEME), "name": "Cobalt Night", "base": "dark", "accent": "cobalt",
     "header": {**DEFAULT_THEME["header"], "pattern": "dots"}},
]

DEFAULTS = {
    "sd_scripts_dir": "",
    "launcher": "accelerate",            # accelerate | python
    "accelerate_args": "--num_cpu_threads_per_process 4",
    "default_output_dir": "",
    "torch_index_url": "https://download.pytorch.org/whl/cu128",
    "swarm_dir": "",
    "swarm_url": "http://127.0.0.1:7801",
    "swarm_lora_dir": "",
    "autocomplete_csv": "",
    "comfy_mode": "",            # swarm | standalone ("" = pick automatically)
    "comfy_dir": "",
    "comfy_url": "http://127.0.0.1:8188",
    "comfy_lora_dir": "",
    "notify_on_finish": True,
    "theme": DEFAULT_THEME,
    "onboarded": False,
    "default_preset": "",
    "check_app_updates": True,   # look for a newer LoRA Studio on GitHub (a few times a day at most)        # preset that new training sessions start from ("" = none)
}

_lock = threading.Lock()


def _path():
    return paths.data_dir() / "settings.json"


def load():
    data = read_json(_path(), {}) or {}
    merged = copy.deepcopy(DEFAULTS)
    merged.update(data)
    theme = copy.deepcopy(DEFAULT_THEME)
    theme.update(merged.get("theme") or {})
    theme["header"] = {**DEFAULT_THEME["header"], **(theme.get("header") or {})}
    merged["theme"] = theme
    return merged


def save(patch):
    with _lock:
        cur = load()
        cur.update(patch or {})
        write_json(_path(), cur)
        return cur


def get(key):
    return load().get(key, DEFAULTS.get(key))


# ---- themes -------------------------------------------------------------

def list_themes():
    user = []
    for f in sorted(paths.themes_dir().glob("*.json")):
        t = read_json(f)
        if isinstance(t, dict) and t.get("name"):
            t["user"] = True
            user.append(t)
    return [dict(t, user=False) for t in BUILTIN_THEMES] + user


def save_theme(theme):
    theme = dict(theme)
    theme.pop("user", None)
    name = theme.get("name") or "My Theme"
    write_json(paths.themes_dir() / f"{safe_name(name)}.json", theme)
    return list_themes()


def delete_theme(name):
    f = paths.themes_dir() / f"{safe_name(name)}.json"
    if f.exists():
        f.unlink()
    return list_themes()
