"""CSS themes: .css files you drop into Settings > Appearance.

They live in the data folder (css-themes/), so app updates never touch them. The one in use is
named by settings theme["css"] and is loaded before web/css/custom.css, so custom.css still wins.
"""
from pathlib import Path

from . import paths
from .util import safe_name

MAX_BYTES = 8 * 1024 * 1024   # themes with embedded fonts and pictures are ~100 KB; this is plenty


def _dir() -> Path:
    return paths.sub("css-themes")


def clean_name(name):
    name = Path(str(name or "")).name
    if name.lower().endswith(".css"):
        name = name[:-4]
    name = safe_name(name.strip().strip("."))
    return name[:80] or "My theme"


def _file(name) -> Path:
    return _dir() / f"{clean_name(name)}.css"


def list_themes():
    return [{"name": f.stem, "size": f.stat().st_size}
            for f in sorted(_dir().glob("*.css"), key=lambda f: f.stem.lower())]


def add(name, text):
    """Save a theme (replacing one with the same name). Returns (saved name, the list)."""
    if not isinstance(text, str):
        raise RuntimeError("That file couldn't be read as text.")
    if "\x00" in text:
        raise RuntimeError("That doesn't look like a CSS file.")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise RuntimeError("That CSS file is over 8 MB, which is too big for a theme.")
    f = _file(name)
    f.write_text(text, encoding="utf-8")
    return f.stem, list_themes()


def add_from_path(path):
    p = Path(path)
    if p.suffix.lower() != ".css":
        raise RuntimeError("Pick a .css file.")
    if p.stat().st_size > MAX_BYTES:
        raise RuntimeError("That CSS file is over 8 MB, which is too big for a theme.")
    return add(p.name, p.read_text(encoding="utf-8", errors="replace"))


def read(name):
    f = _file(name)
    return f.read_text(encoding="utf-8", errors="replace") if name and f.is_file() else ""


def delete(name):
    f = _file(name)
    if f.is_file():
        f.unlink()
    return list_themes()
