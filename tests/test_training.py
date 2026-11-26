"""Training: writing training.toml, reading a script's options, the check before training,
the queue, presets, samples, run folders, safety while training and copying to SwarmUI."""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from PIL import Image

from helpers import ROOT, img
from studio import preflight, tomlio


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


def test_preflight_catches_common_mistakes(tmp_path):
    d = tmp_path / "imgs"; d.mkdir(); img(d / "1.png")
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
    d = tmp_path / "imgs"; d.mkdir(); img(d / "1.png"); (d / "1.txt").write_text("1girl")
    issues = preflight.check({"script": "x.py", "args": {"learning_rate": "3e-5"},
                              "schema_args": [{"key": "learning_rate", "kind": "float"}],
                              "dataset": {"subsets": [{"image_dir": str(d)}]}})
    assert issues == []


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


def test_sample_gif(tmp_path):
    from studio import samples
    (tmp_path / "sample").mkdir()
    for ep in (1, 2, 3):
        img(tmp_path / "sample" / f"t_e{ep:06d}_00_20261106120{ep}00.png", (512, 512))
    gif = samples.make_gif({"config": {"output_dir": str(tmp_path), "output_name": "t"}}, 0)
    with Image.open(gif) as im:
        assert im.n_frames == 3


def test_each_run_gets_its_own_folder(tmp_path, monkeypatch):
    from studio import settings, trainer
    monkeypatch.setattr(settings, "get", lambda k, *a: True if k == "run_folders" else None)
    t = trainer.Trainer.__new__(trainer.Trainer)
    out = tmp_path / "model"
    def start(cfg):
        run = {"id": "x", "config": dict(cfg)}
        d = tmp_path / "rundir"; d.mkdir(exist_ok=True)
        monkeypatch.setattr(trainer, "save_run", lambda r: None)
        t._own_folder(run, d)
        Path(run["config"]["output_dir"], "lora.safetensors").write_text("x")   # pretend it trained
        return run["config"]["output_dir"]
    a = start({"output_dir": str(out), "output_name": "shion_v1"})
    b = start({"output_dir": str(out), "output_name": "shion_v1"})          # same name, queued after
    c = start({"output_dir": b, "output_name": "shion_v1"})                 # re-run of the second one
    d = start({"output_dir": str(out), "output_name": "bad:name"})
    assert [Path(x).name for x in (a, b, c, d)] == ["shion_v1", "shion_v1 (2)", "shion_v1 (3)", "bad_name"]
    assert all(Path(x).parent == out for x in (a, b, c, d))


def _api_with_running(monkeypatch, image_dir, name="Shion"):
    from studio import api as api_mod, trainer
    a = api_mod.Api()
    monkeypatch.setattr(a._trainer, "state", lambda: {"current": {"id": "r1", "name": name}, "queue": []})
    monkeypatch.setattr(trainer, "load_run", lambda rid: {"id": rid, "name": name,
                                                          "dataset": {"subsets": [{"image_dir": str(image_dir)}]}})
    return a


def test_images_of_the_running_training_are_protected(tmp_path, monkeypatch):
    ds = tmp_path / "shion"; ds.mkdir(); img(ds / "1.png")
    other = tmp_path / "other"; other.mkdir(); img(other / "1.png")
    a = _api_with_running(monkeypatch, ds)
    for call in (lambda: a.ds_move([str(ds / "1.png")]), lambda: a.ds_rename(str(ds)),
                 lambda: a.ds_crop(str(ds / "1.png"), [0, 0, 10, 10]), lambda: a.ds_batch_resize({"folder": str(ds)})):
        with pytest.raises(RuntimeError, match="being used by the training"):
            call()
    a.ds_save_caption(str(ds / "1.txt"), "1girl")            # captions are fine
    assert a.ds_in_use(str(ds))["running"] == "Shion" and a.ds_in_use(str(other))["running"] is None
    a.ds_move([str(other / "1.png")])                        # other folders are fine


def test_no_sd_scripts_update_during_training(tmp_path, monkeypatch):
    a = _api_with_running(monkeypatch, tmp_path)
    for call in (a.sd_update, a.sd_rollback, lambda: a.sd_switch_branch("dev")):
        with pytest.raises(RuntimeError, match="A training is running"):
            call()


def test_copies_to_swarm_never_overwrite_another_run(tmp_path, monkeypatch):
    from studio import runs, swarm, trainer
    base = tmp_path / "Lora"
    def run_with(content, own):
        f = tmp_path / own / "shion_v1.safetensors"; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(content)
        r = {"id": own, "config": {"output_name": "shion_v1"}, "own_folder": str(f.parent)}
        monkeypatch.setattr(trainer, "load_run", lambda rid: r)
        monkeypatch.setattr(trainer, "save_run", lambda run: None)
        monkeypatch.setattr(runs, "outputs", lambda run: [{"path": str(f), "name": f.name}])
        return swarm.copy_run_outputs(own, "final", str(base), "swarm")["folder"]
    a = run_with("first", "shion_v1")
    b = run_with("second", "shion_v1 (2)")
    run_with("third", "old_style")       # an older run whose folder name clashes with nothing
    assert Path(a).name == "shion_v1" and Path(b).name == "shion_v1 (2)"
    assert (Path(a) / "shion_v1.safetensors").read_text() == "first"
