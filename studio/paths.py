"""Where LoRA Studio keeps its own files (settings, runs, presets, themes).

Windows: %APPDATA%\\LoRA Studio
Linux:   ~/.local/share/lora-studio  (or $XDG_DATA_HOME/lora-studio)
         An existing ~/.lora_studio folder keeps being used, so nothing gets lost.
Override with the LORA_STUDIO_HOME environment variable (handy for testing).
"""
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = APP_DIR / "web"


def data_dir() -> Path:
    override = os.environ.get("LORA_STUDIO_HOME")
    if override:
        base = Path(override)
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / "LoRA Studio"
    else:
        legacy = Path.home() / ".lora_studio"
        if legacy.is_dir():
            base = legacy
        else:
            xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
            base = Path(xdg) / "lora-studio"
    base.mkdir(parents=True, exist_ok=True)
    return base


def sub(name: str) -> Path:
    p = data_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def runs_dir() -> Path:
    return sub("runs")


def presets_dir() -> Path:
    return sub("presets")


def themes_dir() -> Path:
    return sub("themes")


def cache_dir() -> Path:
    return sub("cache")
