"""Update LoRA Studio itself, from inside the app.

Two ways, depending on how LoRA Studio was installed:
- a git folder (cloned, or GitHub Desktop): `git pull --ff-only`, so local work is never overwritten;
- a zip download: the release zip is downloaded from GitHub and copied over this folder.

Never touched: the .venv (the app's own Python), .git, your custom.css, and your data
(settings, runs, presets), which lives in a separate folder anyway.
Afterwards any new requirements are installed and the app can restart itself.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from . import appupdate
from .util import CREATE_NO_WINDOW

ROOT = Path(__file__).resolve().parents[1]
# Never copied over when updating from a zip.
KEEP = {".venv", "venv", ".git", "__pycache__", ".pytest_cache", "node_modules"}
KEEP_FILES = {"web/css/custom.css"}   # your own styles


def method():
    if (ROOT / ".git").exists() and shutil.which("git"):
        return "git"
    return "zip"


def info():
    """How this install would update (shown before you click)."""
    m = method()
    out = {"method": m, "folder": str(ROOT).replace("\\", "/")}
    if m == "git":
        code, txt = _git("status", "--porcelain", "--untracked-files=no")
        out["local_changes"] = bool(txt.strip()) if code == 0 else None
        _, br = _git("rev-parse", "--abbrev-ref", "HEAD")
        out["branch"] = br.strip()
    return out


def _git(*args, timeout=120):
    try:
        p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def _download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "LoRA-Studio"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _zip_url(tag):
    return f"https://github.com/{appupdate.REPO}/archive/refs/tags/{tag}.zip"


def update(task, tag=None):
    """Bring this folder up to the latest release. Returns {"updated": bool, "restart": bool}."""
    if method() == "git":
        changed = _update_git(task)
    else:
        if not tag:
            latest = (appupdate.check(force=True) or {}).get("latest")
            if not latest:
                raise RuntimeError("Couldn't find the latest release on GitHub. Check your internet connection.")
            tag = latest["tag"]
        changed = _update_zip(task, tag)
    _requirements(task)
    task.log("\nDone. Restart LoRA Studio to use the new version." if changed else "\nYou already have the latest files.")
    return {"updated": changed, "restart": changed}


def _update_git(task):
    task.log("This LoRA Studio folder uses git, so it's updated with git pull.")
    code, txt = _git("status", "--porcelain", "--untracked-files=no")
    if code == 0 and txt.strip():
        raise RuntimeError("This folder has changes of its own (shown in GitHub Desktop), so it isn't updated "
                           "automatically. Commit or discard them, or use Pull origin in GitHub Desktop.")
    _, before = _git("rev-parse", "HEAD")
    task.progress = {"n": 1, "total": 3, "msg": "Fetching the latest version…"}
    code, out = _git("pull", "--ff-only", timeout=300)
    task.log(out.strip())
    if code != 0:
        raise RuntimeError("git pull didn't work (see the log). In GitHub Desktop, use Fetch origin, then Pull origin.")
    _, after = _git("rev-parse", "HEAD")
    return before.strip() != after.strip()


def _update_zip(task, tag):
    task.log(f"Downloading LoRA Studio {tag} from GitHub…")
    task.progress = {"n": 1, "total": 3, "msg": f"Downloading {tag}…"}
    tmp = Path(tempfile.mkdtemp(prefix="lorastudio_update_"))
    try:
        z = tmp / "release.zip"
        _download(_zip_url(tag), z)
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():             # refuse anything that would land outside the folder
                if name.startswith("/") or ".." in Path(name).parts:
                    raise RuntimeError("The downloaded file looks wrong, so nothing was changed.")
            zf.extractall(tmp / "x")
        tops = [d for d in (tmp / "x").iterdir() if d.is_dir()]
        if len(tops) != 1 or not (tops[0] / "main.py").exists() or not (tops[0] / "studio").is_dir():
            raise RuntimeError("The download isn't a LoRA Studio release, so nothing was changed.")
        src = tops[0]
        task.progress = {"n": 2, "total": 3, "msg": "Copying the new files…"}
        n = 0
        for f in src.rglob("*"):
            rel = f.relative_to(src)
            if set(rel.parts) & KEEP or rel.as_posix() in KEEP_FILES:
                continue
            target = ROOT / rel
            if f.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
                n += 1
        task.log(f"Updated {n} files (your .venv and custom.css were kept).")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _requirements(task):
    req = ROOT / "requirements.txt"
    if not req.exists():
        return
    task.progress = {"n": 3, "total": 3, "msg": "Checking requirements…"}
    py = sys.executable
    if py.lower().endswith("pythonw.exe"):        # the windowless Python can't show pip's output
        alt = Path(py).with_name("python.exe")
        py = str(alt) if alt.exists() else py
    code = task.stream([py, "-m", "pip", "install", "-q", "-r", str(req)], cwd=str(ROOT))
    if code != 0:
        task.log("Couldn't install the requirements. Run Install.bat (or ./install.sh) once by hand.")


def restart(argv=None):
    """Start a fresh LoRA Studio and let this one close. The new one waits for the old one's port."""
    rest = [a for a in (argv if argv is not None else sys.argv[1:]) if a != "--wait-port"]
    args = [sys.executable, str(ROOT / "main.py"), *rest, "--wait-port"]
    kw = {"cwd": str(ROOT)}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen(args, **kw)
    return True
