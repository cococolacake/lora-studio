"""How long will a run take? Learned from your own past runs."""
import statistics

from . import health, paths
from .util import read_json


def _past_runs():
    out = []
    for d in paths.runs_dir().iterdir():
        r = read_json(d / "run.json")
        if not r or r.get("status") not in ("done", "stopped", "failed", "interrupted"):
            continue
        p = r.get("progress") or {}
        if not p.get("step") or not p.get("elapsed"):
            continue
        ds = r.get("dataset") or {}
        res = ds.get("resolution") or [1024, 1024]
        try:
            area = int(res[0]) * int(res[1])
        except (TypeError, ValueError, IndexError):
            area = 1024 * 1024
        overhead = None
        if r.get("status") == "done" and r.get("started") and r.get("finished"):
            overhead = max(0.0, (r["finished"] - r["started"]) - p["elapsed"])
        out.append({"script": r.get("script"), "family": r.get("family"), "sps": p["elapsed"] / p["step"],
                    "area": area, "batch": int(ds.get("batch_size") or 1), "overhead": overhead})
    return out


def _steps(job):
    args = job.get("args") or {}
    ds = job.get("dataset") or {}
    epochs = int(args.get("max_train_epochs") or 0)
    check = health.check({**ds, "epochs": epochs or 1, "grad_accum": int(args.get("gradient_accumulation_steps") or 1)})
    per_epoch = check["steps"]["steps_per_epoch"]
    if epochs:
        total = per_epoch * epochs
    else:  # sd-scripts falls back to max_train_steps (default 1600)
        total = int(args.get("max_train_steps") or 1600)
        epochs = round(total / per_epoch, 1) if per_epoch else 0
    return {"images": check["total_images"], "steps_per_epoch": per_epoch, "total_steps": total, "epochs": epochs}


def estimate(job):
    out = _steps(job)
    ds = job.get("dataset") or {}
    res = ds.get("resolution") or [1024, 1024]
    area, batch = int(res[0]) * int(res[1]), int(ds.get("batch_size") or 1)
    past = _past_runs()
    for basis, pick in (("this script", lambda r: r["script"] == job.get("script")),
                        ("this model family", lambda r: r["family"] and r["family"] == job.get("family")),
                        ("all your runs", lambda r: True)):
        same = [r for r in past if pick(r)]
        if same:
            break
    else:
        return {**out, "seconds": None, "based_on": 0}
    # bigger images / batches take proportionally longer per step (rough but useful)
    sps = statistics.median(r["sps"] * (area * batch) / (r["area"] * r["batch"]) for r in same)
    overheads = [r["overhead"] for r in same if r["overhead"] is not None]
    overhead = statistics.median(overheads) if overheads else 60.0
    return {**out, "seconds": out["total_steps"] * sps + overhead, "sec_per_step": sps,
            "based_on": len(same), "basis": basis}


def safe_estimate(job):
    try:
        return estimate(job)
    except Exception:
        return None

