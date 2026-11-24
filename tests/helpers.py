"""Shared by the tests: the import path, a temporary data folder, and a picture maker.

Quick checks that run on every pull request (GitHub Actions) and with `python -m pytest`.
Each test guards something that broke before, or that would be painful to break.
No GPU, sd-scripts or internet needed.
"""
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LORA_STUDIO_HOME", tempfile.mkdtemp(prefix="lshome_"))


def img(path, size=(800, 800)):
    Image.new("RGB", size, (240, 180, 220)).save(path)
