"""Run a worker script (studio/workers/*.py) inside the sd-scripts venv and track it as a Task."""
import json
import os
from pathlib import Path

from . import paths, sdscripts
from .util import Task, new_id, write_json

WORKERS = Path(os.environ.get("LORA_STUDIO_WORKERS_DIR") or Path(__file__).with_name("workers"))


def _python():
    repo = sdscripts.root()
    py = sdscripts.venv_python(repo) if repo else None
    if not py:
        raise RuntimeError("This tool runs in your sd-scripts venv, which wasn't found. Set up sd-scripts first.")
    return py, repo


def run(title, worker, job, on_result=None):
    """Start worker in the background; returns the Task."""
    py, repo = _python()

    def go(task):
        job_file = paths.sub("cache/jobs") / f"{new_id()}.json"
        write_json(job_file, job)

        def on_line(line):
            if line.startswith("@@P "):
                task.progress = json.loads(line[4:])
                if task.progress.get("msg") and task.progress.get("n", 0) == 0:
                    task.log(task.progress["msg"])
                return True
            if line.startswith("@@R "):
                task.result = json.loads(line[4:])
                return True
            if line.startswith("@@MISSING "):
                task.missing = line[10:].strip()
                task.log(f"The sd-scripts venv is missing the '{task.missing}' package.")
                return True
            return False

        code = task.stream([py, str(WORKERS / f"{worker}.py"), str(job_file)], cwd=str(repo), on_line=on_line)
        job_file.unlink(missing_ok=True)
        if code != 0 or task.result is None:
            task.finish(False, task.result)
            return None
        if on_result:
            on_result(task.result)
        return task.result

    return Task.spawn(title, go)


def install_package(pkg):
    """pip install a missing package into the sd-scripts venv."""
    py, repo = _python()
    allowed = {"timm", "transformers", "huggingface-hub", "numpy", "pillow"}
    if pkg not in allowed:
        raise RuntimeError(f"Won't install unknown package {pkg!r}.")

    def go(task):
        if task.stream([py, "-m", "pip", "install", pkg], cwd=str(repo)) != 0:
            task.finish(False)

    return Task.spawn(f"Installing {pkg} into sd-scripts", go)
