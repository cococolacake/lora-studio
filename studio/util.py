"""Small shared helpers."""
import json
import os
import re
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# Hide console windows for child processes on Windows.
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def fmt_duration(s):
    s = int(max(0, s or 0))
    h, m = s // 3600, (s % 3600) // 60
    return f"{h}h {m:02d}m" if h else f"{m}m {s % 60:02d}s" if m else f"{s}s"


def new_id(prefix=""):
    return prefix + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def is_image(name):
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip() or "untitled"


def split_cli_args(text):
    """Split a typed argument string like '--a 1 --b "C:/x y"' into a list."""
    text = " ".join((text or "").split())
    if not text:
        return []
    if os.name == "nt":
        parts = shlex.split(text, posix=False)
        return [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    return shlex.split(text)


def run(cmd, cwd=None, timeout=120, env=None):
    """Run a short command and return (returncode, combined output)."""
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=env, creationflags=CREATE_NO_WINDOW,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError as e:
        return 127, str(e)
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def open_in_explorer(path):
    path = str(path)
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 - opening a folder the user chose
    else:
        subprocess.Popen(["xdg-open", path])


def child_env():
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"       # stream logs live
    env["PYTHONIOENCODING"] = "utf-8"   # tqdm bars won't crash the reader
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    return env


def kill_tree(proc):
    """Stop a process and all of its children."""
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/f", "/t", "/pid", str(proc.pid)],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    else:
        import signal
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            proc.terminate()


def popen_kwargs():
    """Popen options so kill_tree can stop the whole tree."""
    if os.name == "nt":
        return {"creationflags": CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


class Task:
    """A long-running background job (update, clone, health scan) with a log the UI can poll."""

    _all = {}
    _lock = threading.Lock()

    def __init__(self, title):
        self.id = uuid.uuid4().hex[:10]
        self.title = title
        self.lines = []
        self.status = "running"   # running | done | failed
        self.result = None
        self.proc = None
        self.progress = None      # {"n", "total", "msg"} for workers that report it
        self.missing = None       # a package the sd-scripts venv lacks
        with Task._lock:
            Task._all[self.id] = self

    def log(self, text):
        for line in str(text).splitlines() or [""]:
            self.lines.append(line)
        if len(self.lines) > 5000:
            del self.lines[:1000]

    def stream(self, cmd, cwd=None, env=None, on_line=None):
        """Run a command, piping its output into this task's log. Returns exit code.
        on_line(line) may return True to keep a line out of the log."""
        self.log("$ " + " ".join(str(c) for c in cmd))
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=cwd, env=env or child_env(), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                **popen_kwargs(),
            )
        except FileNotFoundError as e:
            self.log(f"Could not start: {e}")
            return 127
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            if on_line and on_line(line):
                continue
            self.log(line)
        self.proc.wait()
        return self.proc.returncode

    def finish(self, ok=True, result=None):
        self.status = "done" if ok else "failed"
        self.result = result

    def snapshot(self, since=0):
        return {"id": self.id, "title": self.title, "status": self.status,
                "lines": self.lines[since:], "total": len(self.lines), "result": self.result,
                "progress": self.progress, "missing": self.missing}

    def cancel(self):
        kill_tree(self.proc)
        self.log("Cancelled.")
        self.finish(False)

    @classmethod
    def get(cls, tid):
        return cls._all.get(tid)

    @classmethod
    def spawn(cls, title, fn, *args):
        """Start fn(task, *args) in a thread; fn returns result or raises."""
        task = cls(title)

        def runner():
            try:
                res = fn(task, *args)
                if task.status == "running":
                    task.finish(True, res)
            except Exception as e:  # report any failure to the UI log
                task.log(f"Error: {e}")
                task.finish(False)

        threading.Thread(target=runner, daemon=True).start()
        return task
