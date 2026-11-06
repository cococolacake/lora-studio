"""Find, inspect, install and update a kohya-ss/sd-scripts checkout."""
import os
import re
import shutil
import sys
from pathlib import Path

from . import paths, settings
from .util import Task, read_json, run, write_json

REPO_URL = "https://github.com/kohya-ss/sd-scripts.git"

# Filename prefix -> human family name. Order matters (longest first).
FAMILIES = [
    ("hunyuan_image_", "HunyuanImage"),
    ("lumina_", "Lumina"),
    ("anima_", "Anima"),
    ("flux_", "FLUX"),
    ("sd3_", "SD3"),
    ("sdxl_", "SDXL"),
    ("", "SD 1.x / 2.x"),
]

NOT_TRAINERS = {"train_util.py"}


# ---- locating -----------------------------------------------------------

def root():
    p = settings.get("sd_scripts_dir")
    return Path(p) if p else None


def is_sd_scripts(path):
    p = Path(path)
    return (p / "train_network.py").is_file() and (p / "library").is_dir()


def venv_dir(repo):
    for name in ("venv", ".venv"):
        d = Path(repo) / name
        if d.is_dir():
            return d
    return None


def venv_python(repo):
    v = venv_dir(repo)
    if v:
        for c in (v / "Scripts" / "python.exe", v / "bin" / "python", v / "bin" / "python3"):
            if c.exists():
                return str(c)
    return None


def accelerate_exe(repo):
    v = venv_dir(repo)
    if v:
        for c in (v / "Scripts" / "accelerate.exe", v / "bin" / "accelerate"):
            if c.exists():
                return str(c)
    return None


def guess_locations():
    """Common places people keep sd-scripts, for the first-run wizard."""
    home = Path.home()
    cands = [home / "sd-scripts", home / "Desktop" / "sd-scripts", Path("C:/sd-scripts"),
             home / "Desktop" / "Work" / "sd-scripts", home / "Documents" / "sd-scripts"]
    return [str(c) for c in cands if is_sd_scripts(c)]


# ---- git ----------------------------------------------------------------

def git(repo, *args, timeout=60):
    return run(["git", "-C", str(repo), *args], timeout=timeout)


def status(fetch=False):
    repo = root()
    if not repo:
        return {"configured": False}
    if not is_sd_scripts(repo):
        return {"configured": True, "valid": False, "path": str(repo)}
    info = {"configured": True, "valid": True, "path": str(repo),
            "venv": bool(venv_python(repo)), "accelerate": bool(accelerate_exe(repo))}
    code, _ = git(repo, "rev-parse", "--is-inside-work-tree")
    info["git"] = code == 0
    if code != 0:
        return info
    fetch_err = None
    if fetch:
        c, out = git(repo, "fetch", "--prune", "origin", timeout=120)
        if c != 0:
            fetch_err = out.strip()[-300:]
    _, branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    _, head = git(repo, "log", "-1", "--format=%h|%H|%cr|%ci|%s")
    _, dirty = git(repo, "status", "--porcelain", "--untracked-files=no")
    h = head.strip().split("|", 4)
    info.update({
        "branch": branch.strip(),
        "commit": h[0] if h else "",
        "commit_full": h[1] if len(h) > 1 else "",
        "commit_age": h[2] if len(h) > 2 else "",
        "commit_date": h[3] if len(h) > 3 else "",
        "commit_subject": h[4] if len(h) > 4 else "",
        "dirty": bool(dirty.strip()),
        "fetch_error": fetch_err,
    })
    code, counts = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{u}")
    if code == 0 and counts.strip():
        ahead, behind = counts.split()
        info["ahead"], info["behind"] = int(ahead), int(behind)
    else:
        info["ahead"] = info["behind"] = None
    hist = read_json(_history_file(), [])
    info["can_rollback"] = bool(hist)
    return info


def changelog(limit=60):
    """Commits on the upstream branch that aren't checked out yet."""
    repo = root()
    code, out = git(repo, "log", f"-{limit}", "--format=%h|%an|%cr|%s", "HEAD..@{u}")
    if code != 0:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            rows.append(dict(zip(("commit", "author", "age", "subject"), parts)))
    return rows


def recent_commits(limit=15):
    repo = root()
    code, out = git(repo, "log", f"-{limit}", "--format=%h|%an|%cr|%s")
    if code != 0:
        return []
    return [dict(zip(("commit", "author", "age", "subject"), l.split("|", 3)))
            for l in out.splitlines() if l.count("|") >= 3]


def branches():
    repo = root()
    code, out = git(repo, "branch", "-r", "--format=%(refname:short)|%(committerdate:relative)",
                    "--sort=-committerdate")
    if code != 0:
        return []
    res = []
    for line in out.splitlines():
        name, _, age = line.partition("|")
        if "->" in name or name.endswith("/HEAD") or "/" not in name:
            continue
        res.append({"name": name.split("/", 1)[1], "age": age})
    return res


def _history_file():
    return paths.data_dir() / "sdscripts_history.json"


def _remember_commit(repo):
    _, h = git(repo, "rev-parse", "HEAD")
    _, b = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    hist = read_json(_history_file(), []) or []
    hist.append({"commit": h.strip(), "branch": b.strip()})
    write_json(_history_file(), hist[-20:])


def _pip_install(task, repo):
    py = venv_python(repo)
    if not py:
        task.log("No venv found, so dependencies were not reinstalled.")
        return True
    req = Path(repo) / "requirements.txt"
    if not req.exists():
        return True
    task.log("\nInstalling requirements in the sd-scripts venv...")
    return task.stream([py, "-m", "pip", "install", "-r", "requirements.txt"], cwd=repo) == 0


def _check_clean(task, repo):
    _, dirty = git(repo, "status", "--porcelain", "--untracked-files=no")
    if dirty.strip():
        task.log("You have local edits to sd-scripts files:\n" + dirty)
        task.log("Commit, stash or revert them first (git stash), then try again.")
        return False
    return True


def update(task, install_deps=True):
    repo = root()
    if not _check_clean(task, repo):
        task.finish(False)
        return
    _remember_commit(repo)
    if task.stream(["git", "-C", str(repo), "pull", "--ff-only"]) != 0:
        task.log("git pull failed.")
        task.finish(False)
        return
    if install_deps and not _pip_install(task, repo):
        task.finish(False)
        return
    _schema_cache_clear()
    task.log("\nsd-scripts is up to date.")


def switch_branch(task, branch, install_deps=True):
    repo = root()
    if not _check_clean(task, repo):
        task.finish(False)
        return
    _remember_commit(repo)
    task.stream(["git", "-C", str(repo), "fetch", "origin"])
    code = task.stream(["git", "-C", str(repo), "checkout", branch])
    if code != 0:
        code = task.stream(["git", "-C", str(repo), "checkout", "-b", branch, "--track", f"origin/{branch}"])
    if code != 0:
        task.finish(False)
        return
    task.stream(["git", "-C", str(repo), "pull", "--ff-only"])
    if install_deps:
        _pip_install(task, repo)
    _schema_cache_clear()
    task.log(f"\nNow on branch {branch}.")


def rollback(task, install_deps=True):
    repo = root()
    hist = read_json(_history_file(), []) or []
    if not hist:
        task.log("Nothing to roll back to.")
        task.finish(False)
        return
    if not _check_clean(task, repo):
        task.finish(False)
        return
    prev = hist.pop()
    write_json(_history_file(), hist)
    task.stream(["git", "-C", str(repo), "checkout", prev["branch"]])
    if task.stream(["git", "-C", str(repo), "reset", "--hard", prev["commit"]]) != 0:
        task.finish(False)
        return
    if install_deps:
        _pip_install(task, repo)
    _schema_cache_clear()
    task.log(f"\nRolled back to {prev['commit'][:8]} on {prev['branch']}.")


def _default_python():
    """Python to build sd-scripts' venv with: 3.10 (recommended) or 3.11 if installed."""
    if os.name == "nt":
        return ["py", "-3.10"]
    for name in ("python3.10", "python3.11"):
        exe = shutil.which(name)
        if exe:
            return [exe]
    return [sys.executable]


def install(task, dest, branch="main", python_cmd="", torch_index=""):
    """Clone sd-scripts and build its venv (torch + requirements + accelerate)."""
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        if is_sd_scripts(dest):
            task.log("sd-scripts already exists there; using it.")
        else:
            task.log(f"{dest} is not empty. Pick an empty folder.")
            task.finish(False)
            return
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if task.stream(["git", "clone", "--branch", branch, REPO_URL, str(dest)]) != 0:
            task.finish(False)
            return
    if not venv_python(dest):
        py = python_cmd.split() if python_cmd else _default_python()
        task.log("\nCreating venv...")
        if task.stream([*py, "-m", "venv", "venv"], cwd=dest) != 0:
            task.log("Could not create the venv. Install Python 3.10 (sd-scripts' recommended version) and retry.")
            if os.name != "nt":
                task.log("On Debian/Ubuntu you may also need the venv package, e.g.  sudo apt install python3.10-venv")
            task.finish(False)
            return
    vpy = venv_python(dest)
    task.stream([vpy, "-m", "pip", "install", "--upgrade", "pip"], cwd=dest)
    index = torch_index or settings.get("torch_index_url")
    task.log("\nInstalling PyTorch (this is the big download)...")
    if task.stream([vpy, "-m", "pip", "install", "torch", "torchvision", "--index-url", index], cwd=dest) != 0:
        task.finish(False)
        return
    if not _pip_install(task, dest):
        task.finish(False)
        return
    settings.save({"sd_scripts_dir": str(dest)})
    task.log("\nAll set. Run `accelerate config` once if you train on multiple GPUs; "
             "single-GPU training works with the defaults.")


# ---- scripts ------------------------------------------------------------

def list_scripts():
    repo = root()
    if not repo or not is_sd_scripts(repo):
        return []
    out = []
    for f in sorted(Path(repo).glob("*.py")):
        name = f.name
        if name in NOT_TRAINERS or "train" not in name:
            continue
        family = next(label for prefix, label in FAMILIES if name.startswith(prefix))
        if "network" in name:
            kind = "LoRA / network"
        elif "textual_inversion" in name:
            kind = "Textual inversion"
        elif "control" in name:
            kind = "ControlNet"
        else:
            kind = "Full fine-tune"
        out.append({"file": name, "family": family, "kind": kind,
                    "label": _pretty(name)})
    order = {label: i for i, (_, label) in enumerate(FAMILIES)}
    out.sort(key=lambda s: (order.get(s["family"], 99), s["kind"] != "LoRA / network", s["file"]))
    return out


def _pretty(fname):
    stem = fname[:-3]
    for prefix, _ in FAMILIES:
        if prefix and stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return re.sub(r"_+", " ", stem).strip().capitalize()


# ---- argument schema ----------------------------------------------------

def _schema_cache_clear():
    for f in paths.cache_dir().glob("schema_*.json"):
        f.unlink(missing_ok=True)


def schema(script, refresh=False):
    """Every argparse option a training script accepts, read from the script itself."""
    repo = root()
    st = status()
    key = (st.get("commit_full") or "nogit")[:12]
    cache = paths.cache_dir() / f"schema_{key}_{script}.json"
    if not refresh:
        cached = read_json(cache)
        if cached:
            return cached
    py = venv_python(repo) or sys.executable
    dumper = Path(__file__).with_name("_schema_dump.py")
    code, out = run([py, str(dumper), str(repo), script], cwd=str(repo), timeout=300)
    m = re.search(r"<<<SCHEMA>>>(.*)<<<END>>>", out, re.S)
    if not m:
        tail = out.strip()[-1500:]
        raise RuntimeError(f"Couldn't read the options of {script}.\n{tail}")
    import json
    data = json.loads(m.group(1))
    write_json(cache, data)
    return data
