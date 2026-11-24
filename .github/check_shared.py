"""Checks that the files LoRA Studio and Lore Studio share still match the other app's copy.

Some files are the same in both apps (the theme engine's colours, CSS themes, the API bridge, the
release and wiki workflows...). When one changes, the other usually should too. This compares each
one with the other app's `main` branch on GitHub, after swapping the app names, and prints a
warning for each that differs. It never fails the checks: a change often lands in one app first.

Usage: python .github/check_shared.py      (run by the Checks workflow; this file is shared too)
"""
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Paths as they are in LoRA Studio; {app} is lora-studio / lore-studio.
SHARED = [
    ".gitattributes",
    ".github/check_shared.py",
    ".github/release_notes.py",
    ".github/workflows/wiki.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    "Install.bat",
    "{app}.sh",
    "LICENSE",
    "studio/appupdate.py",
    "studio/csstheme.py",
    "studio/gpu.py",
    "web/index.html",
    "web/css/custom.css",
    "web/css/tokens.css",
    "web/fonts/Geist-LICENSE.txt",
    "web/fonts/Geist-Variable.woff2",
    "web/fonts/GeistMono-Variable.woff2",
    "web/js/api.js",
    "web/js/csstheme.js",
]

# The same name, spelled as each app spells it.
NAMES = [("LoRA Studio", "Lore Studio"), ("lora-studio", "lore-studio"),
         ("LORA_STUDIO", "LORE_STUDIO"), ("LoRA-Studio", "Lore-Studio")]


def normalize(data: bytes) -> bytes:
    """Both apps' names become APP, so files that differ only by name match. Binary files stay as they are."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    for a, b in NAMES:
        text = text.replace(a, "APP").replace(b, "APP")
    return text.replace("\r\n", "\n").encode("utf-8")


def fetch(repo, path):
    url = f"https://raw.githubusercontent.com/cococolacake/{repo}/main/{path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    me = "lora-studio" if (ROOT / "lora-studio.sh").exists() else "lore-studio"
    other = "lore-studio" if me == "lora-studio" else "lora-studio"
    differ = []
    for p in SHARED:
        here, there = p.replace("{app}", me), p.replace("{app}", other)
        mine = (ROOT / here).read_bytes() if (ROOT / here).is_file() else None
        try:
            theirs = fetch(other, there)
        except OSError as e:
            print(f"::warning::Couldn't reach GitHub to compare shared files ({e}).")
            return
        if mine is None and theirs is None:
            continue
        if mine is None or theirs is None or normalize(mine) != normalize(theirs):
            what = (f"isn't in {other} yet" if theirs is None else
                    f"is in {other} but not here" if mine is None else f"differs from {other}'s copy")
            differ.append(here)
            print(f"::warning file={here}::{here} {what}. Shared files usually change in both apps.")
    print(f"{len(SHARED) - len(differ)} of {len(SHARED)} shared files match {other}.")


if __name__ == "__main__":
    sys.exit(main())
