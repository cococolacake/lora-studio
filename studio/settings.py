"""App settings and themes, stored as JSON in the data folder."""
import copy
import threading

from . import paths
from .util import read_json, safe_name, write_json

_HEADER = {"type": "none"}   # page headers are plain title bars (patterned headers were removed)

DEFAULT_THEME = {
    "name": "Default",
    "style": "glass",
    "family": "default",        # glass colours: default | cool | warm | lilac
    "base": "light",            # light | dark
    "glass": "efficient",       # efficient (see-through, no live blur) | full (live blur) | off
    "simpleWhileTraining": True,  # solid look while a training runs, so it gets the whole GPU
    "font": "geist",            # geist | system
    "header": dict(_HEADER),
}


BUILTIN_THEMES = [
    DEFAULT_THEME,
    {**copy.deepcopy(DEFAULT_THEME), "name": "Cool Glass", "family": "cool"},
    {**copy.deepcopy(DEFAULT_THEME), "name": "Warm Glass", "family": "warm"},
    {**copy.deepcopy(DEFAULT_THEME), "name": "Lilac", "family": "lilac"},
]


def _to_glass(theme):
    """Themes from before the glass look (the classic pastel ones) become the glass Default,
    keeping light or dark mode, so an older setup never lands on a theme that no longer exists."""
    if (theme or {}).get("style") == "glass":
        return theme
    return {**copy.deepcopy(DEFAULT_THEME), "base": (theme or {}).get("base", "light"),
            **({"name": theme["name"]} if theme and theme.get("name") and theme.get("user") else {})}


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
    "run_folders": True,          # each run saves into its own folder: <output dir>/<output name>[ (2)]
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
    saved = data.get("theme") or {}
    theme = copy.deepcopy(DEFAULT_THEME)
    if saved:
        theme.update(_to_glass(saved))
    theme["header"] = dict(_HEADER)   # patterned headers were removed
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
    user = [dict(_to_glass(t), name=t.get("name", "My theme"), user=True) for t in user]
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
