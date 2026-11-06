"""Run history: list, inspect, resume, re-run and delete past trainings."""
import csv
import shutil
from pathlib import Path

from . import paths, trainer
from .util import natural_key, read_json


def _summary(r):
    prog = r.get("progress") or {}
    dur = None
    if r.get("started"):
        dur = (r.get("finished") or __import__("time").time()) - r["started"]
    return {
        "id": r["id"], "name": r.get("name"), "script": r.get("script"), "family": r.get("family"),
        "status": r.get("status"), "created": r.get("created"), "started": r.get("started"),
        "finished": r.get("finished"), "duration": dur, "loss": prog.get("loss"),
        "step": prog.get("step"), "total": prog.get("total"), "epoch": prog.get("epoch"),
        "epochs": prog.get("epochs"), "sd_commit": r.get("sd_commit"),
    }


def list_runs():
    out = []
    root = paths.runs_dir()
    for d in root.iterdir():
        r = read_json(d / "run.json")
        if r:
            out.append(_summary(r))
    out.sort(key=lambda r: r.get("created") or 0, reverse=True)
    return out


def state_dirs(run):
    """Saved training states (from --save_state) that this run can be resumed from."""
    cfg = run.get("config") or {}
    out_dir, name = cfg.get("output_dir"), cfg.get("output_name")
    if not out_dir or not Path(out_dir).is_dir():
        return []
    found = []
    for d in Path(out_dir).iterdir():
        if d.is_dir() and d.name.endswith("-state") and (not name or d.name.startswith(name)):
            found.append({"path": str(d).replace("\\", "/"), "name": d.name,
                          "mtime": d.stat().st_mtime})
    found.sort(key=lambda x: natural_key(x["name"]), reverse=True)
    return found


def outputs(run):
    cfg = run.get("config") or {}
    out_dir, name = cfg.get("output_dir"), cfg.get("output_name") or ""
    if not out_dir or not Path(out_dir).is_dir():
        return []
    files = [f for f in Path(out_dir).glob(f"{name}*.safetensors") if not f.stem.endswith("-best")]
    files.sort(key=lambda f: natural_key(f.name))
    return [{"path": str(f).replace("\\", "/"), "name": f.name,
             "size": f.stat().st_size} for f in files]


def detail(run_id):
    r = trainer.load_run(run_id)
    if not r:
        return None
    d = trainer.run_dir(run_id)
    r["summary"] = _summary(r)
    r["states"] = state_dirs(r)
    r["outputs"] = outputs(r)
    r["training_toml"] = (d / "training.toml").read_text(encoding="utf-8") if (d / "training.toml").exists() else ""
    r["dataset_toml"] = (d / "dataset.toml").read_text(encoding="utf-8") if (d / "dataset.toml").exists() else ""
    r["folder"] = str(d)
    from . import samples, swarm
    r["sample_grid"] = samples.find(r)
    r["swarm_grid"] = swarm.grid(run_id)
    return r


def log(run_id, since=0):
    live = trainer.get().live_log(run_id, since)
    if live:
        return live
    f = trainer.run_dir(run_id) / "log.txt"
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines() if f.exists() else []
    return {"live": False, "lines": lines[since:], "total": len(lines), "progress_line": ""}


def metrics(run_id, since=0):
    live = trainer.get().live_points(run_id, since)
    if live:
        return live
    f = trainer.run_dir(run_id) / "metrics.csv"
    pts = []
    if f.exists():
        with open(f, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    pts.append({"step": int(row["step"]), "epoch": int(row["epoch"] or 0),
                                "loss": float(row["loss"]), "t": float(row["t"] or 0)})
                except (ValueError, KeyError):
                    continue
    return {"live": False, "points": pts[since:], "total": len(pts)}


def job_from_run(run_id, resume_from=None):
    r = trainer.load_run(run_id)
    job = {k: r.get(k) for k in ("name", "script", "family", "args", "dataset", "extra_args", "config",
                                 "lora_info", "trigger", "send_to_swarm", "send_to_comfy", "sample_prompts")}
    job["parent"] = run_id
    if resume_from:
        job["resume_from"] = resume_from
        job["name"] = f"{r.get('name')} (resumed)"
    return job, r


def delete(run_id):
    d = trainer.run_dir(run_id)
    r = read_json(d / "run.json") or {}
    if r.get("status") == "running":
        raise RuntimeError("Stop the run before deleting it.")
    trainer.get().remove(run_id)
    shutil.rmtree(d, ignore_errors=True)


def set_best(run_id, path):
    """Copy the chosen epoch to <output_name>-best.safetensors and remember it."""
    import re
    r = trainer.load_run(run_id)
    src = Path(path)
    if not src.exists():
        raise RuntimeError("That file no longer exists.")
    name = (r.get("config") or {}).get("output_name") or src.stem
    dest = src.with_name(f"{name}-best.safetensors")
    shutil.copy2(src, dest)
    m = re.search(r"-(\d{6})$", src.stem)
    epoch = int(m.group(1)) if m else ((r.get("progress") or {}).get("epochs") or None)
    r["best"] = {"source": src.name, "path": str(dest).replace("\\", "/"), "epoch": epoch}
    trainer.save_run(r)
    return r["best"]
