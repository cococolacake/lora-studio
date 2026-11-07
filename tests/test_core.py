"""Quick checks that run on every pull request (GitHub Actions) and with `python -m pytest`.

Each test guards something that broke before, or that would be painful to break.
No GPU, sd-scripts or internet needed.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LORA_STUDIO_HOME", tempfile.mkdtemp(prefix="lshome_"))

from studio import appupdate, gallerydl, importer, preflight, tomlio  # noqa: E402
from studio.util import Task  # noqa: E402


# ---- writing training.toml values ------------------------------------------------------------

@pytest.mark.parametrize("kind,raw,want", [
    ("int", "10", 10), ("float", "3e-5", 3e-5), ("number", "100", 100), ("number", "0.1", 0.1),
    ("number", "1e-1", 0.1), ("bool", "true", True), ("str", "", None), ("list", "a=1 b=2", ["a=1", "b=2"]),
])
def test_coerce(kind, raw, want):
    assert tomlio.coerce(kind, raw) == want


def test_number_is_never_quoted():
    # lr_warmup_steps / lr_decay_steps (sd-scripts' int_or_float) must be real numbers (issue #7)
    text = tomlio.dumps({"lr_warmup_steps": tomlio.coerce("number", "100"), "lr_decay_steps": tomlio.coerce("number", "0.1")})
    assert "lr_warmup_steps = 100" in text and "lr_decay_steps = 0.1" in text and '"' not in text


# ---- reading a script's options ------------------------------------------------------------

def test_schema_dump_detects_int_or_float(tmp_path):
    (tmp_path / "fake_train.py").write_text(textwrap.dedent('''
        import argparse
        def int_or_float(v):
            try: return int(v)
            except ValueError: return float(v)
        def setup_parser():
            p = argparse.ArgumentParser()
            p.add_argument("--lr_warmup_steps", type=int_or_float, default=0)
            p.add_argument("--learning_rate", type=float, default=1e-4)
            p.add_argument("--max_train_epochs", type=int)
            p.add_argument("--resolution", type=lambda s: tuple(s.split(",")))
            p.add_argument("--cache_latents", action="store_true")
            return p
    '''))
    out = subprocess.run([sys.executable, str(ROOT / "studio" / "_schema_dump.py"), str(tmp_path), "fake_train.py"],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out.split("<<<SCHEMA>>>", 1)[1].split("<<<END>>>", 1)[0])
    kinds = {a["key"]: a["kind"] for a in data["args"]}
    assert kinds == {"lr_warmup_steps": "number", "learning_rate": "float", "max_train_epochs": "int",
                     "resolution": "str", "cache_latents": "bool"}


# ---- New dataset ------------------------------------------------------------------------------

def _img(path, size=(800, 800)):
    Image.new("RGB", size, (240, 180, 220)).save(path)


def test_build_in_place_keeps_captions_and_bins_small_images(tmp_path):
    d = tmp_path / "ds"
    (d / "_metadata").mkdir(parents=True)
    _img(d / "DATA_1.png"); (d / "DATA_1.txt").write_text("old caption")
    _img(d / "a.jpg"); (d / "_metadata" / "a.jpg.json").write_text(json.dumps({"tags": ["blue", "sky"]}))
    _img(d / "tiny.png", (64, 64))
    r = importer.run(Task("t"), {"source": str(d), "dest": str(d), "min_side": 256})
    assert r["copied"] == 2 and r["too_small"] == 1
    caps = sorted(f.read_text() for f in d.glob("*.txt"))
    assert caps == ["blue, sky", "old caption"]
    assert (d / "_deleted" / "tiny.png").exists()


def test_dataset_only_uses_this_downloads_files(tmp_path):
    dl = tmp_path / "dl"; dl.mkdir()
    for n in ("old1.png", "old2.png", "new1.png"):
        _img(dl / n)
    r = importer.run(Task("t"), {"source": str(dl), "dest": str(tmp_path / "ds"), "min_side": 64,
                                 "files": [str(dl / "new1.png")]})
    assert r["copied"] == 1


def test_build_in_place_refuses_to_mix_downloads(tmp_path):
    dl = tmp_path / "dl"; dl.mkdir()
    _img(dl / "other_artist.png"); _img(dl / "mine.png")
    with pytest.raises(RuntimeError, match="another download"):
        importer.run(Task("t"), {"source": str(dl), "dest": str(dl), "min_side": 64, "files": [str(dl / "mine.png")]})


def test_tidy_metadata(tmp_path):
    _img(tmp_path / "1.png"); (tmp_path / "1.png.json").write_text("{}"); (tmp_path / "settings.json").write_text("{}")
    assert gallerydl.tidy_metadata(tmp_path) == 1
    assert (tmp_path / "_metadata" / "1.png.json").exists() and (tmp_path / "settings.json").exists()


def test_download_folder_named_after_link():
    assert gallerydl.name_from_url("https://www.pixiv.net/en/users/74156805/artworks") == "pixiv users 74156805"


# ---- the check before training -------------------------------------------------------------------

def test_preflight_catches_common_mistakes(tmp_path):
    d = tmp_path / "imgs"; d.mkdir(); _img(d / "1.png")
    issues = preflight.check({
        "script": "x.py",
        "args": {"learning_rate": "abc", "optimizer_type": "Nope", "vae": str(tmp_path / "missing.safetensors"), "output_name": "a:b"},
        "schema_args": [{"key": "learning_rate", "kind": "float"}, {"key": "optimizer_type", "kind": "str", "choices": ["AdamW"]},
                        {"key": "vae", "kind": "str"}, {"key": "output_name", "kind": "str"}],
        "dataset": {"subsets": [{"image_dir": str(d)}]},
    })
    errors = " ".join(x["msg"] for x in issues if x["level"] == "error")
    assert "learning_rate" in errors and "optimizer_type" in errors and "missing.safetensors" in errors and "a:b" in errors


def test_preflight_is_quiet_when_all_is_well(tmp_path):
    d = tmp_path / "imgs"; d.mkdir(); _img(d / "1.png"); (d / "1.txt").write_text("1girl")
    issues = preflight.check({"script": "x.py", "args": {"learning_rate": "3e-5"},
                              "schema_args": [{"key": "learning_rate", "kind": "float"}],
                              "dataset": {"subsets": [{"image_dir": str(d)}]}})
    assert issues == []


# ---- update notice ---------------------------------------------------------------------------

def test_version_order():
    assert appupdate._ver("v0.10.0") > appupdate._ver("0.9.9") > appupdate._ver("v0.6.6") and appupdate._ver("junk") == ()


# ---- when the queue is done ------------------------------------------------------------------

def test_power_countdown_can_be_cancelled_and_resets(monkeypatch):
    import time
    from studio import power
    ran = []
    monkeypatch.setattr(power, "_run", lambda a: ran.append(a))
    monkeypatch.setattr(power, "GRACE", 0.3)
    monkeypatch.setattr("studio.notify.toast", lambda *a, **k: False)
    power.queue_finished()                       # nothing chosen: nothing happens
    assert power.get()["pending"] is None
    power.set_action("sleep"); power.queue_finished(); power.cancel(); time.sleep(0.5)
    assert ran == [] and power.get()["action"] == "none"
    power.set_action("shutdown"); power.queue_finished(); time.sleep(0.6)
    assert ran == ["shutdown"] and power.get()["action"] == "none"


# ---- sharing presets -------------------------------------------------------------------------

def test_shared_preset_has_no_personal_paths(tmp_path):
    from studio.api import Api
    a = Api()
    a.preset_save("share test", {"script": "x.py", "args": {
        "pretrained_model_name_or_path": "C:/Users/me/model.safetensors", "vae": "C:/Users/me/vae.safetensors",
        "output_dir": "C:/Users/me/out", "output_name": "mine", "learning_rate": 3e-5},
        "dataset": {"subsets": [{"image_dir": "C:/Users/me/ds", "num_repeats": 3}]}, "lora_info": {"title": "x", "trigger": "y"}})
    out = a.preset_export("share test", str(tmp_path))
    text = Path(out).read_text()
    assert "C:/Users/me" not in text and "learning_rate" in text and '"num_repeats": 3' in text
    first, second = a.preset_import(out)["name"], a.preset_import(out)["name"]
    assert first != second   # importing never overwrites a preset you have


# ---- sample animation --------------------------------------------------------------------------

def test_sample_gif(tmp_path):
    from studio import samples
    (tmp_path / "sample").mkdir()
    for ep in (1, 2, 3):
        _img(tmp_path / "sample" / f"t_e{ep:06d}_00_20261106120{ep}00.png", (512, 512))
    gif = samples.make_gif({"config": {"output_dir": str(tmp_path), "output_name": "t"}}, 0)
    with Image.open(gif) as im:
        assert im.n_frames == 3
