"""Is there a newer LoRA Studio on GitHub? Checked at most every few hours, quietly; never blocks.

Two ways to follow updates (Settings > About > Update from):
- "release" (the default): the newest GitHub release, compared by version number.
- "main": the newest commit on the main branch, for trying changes before they're released.
"""
import json
import re
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from . import __version__, paths, settings
from .util import CREATE_NO_WINDOW, read_json, write_json

REPO = "cococolacake/lora-studio"
RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=10"
MAIN = f"https://api.github.com/repos/{REPO}/commits/main"
EVERY = 6 * 3600
ROOT = Path(__file__).resolve().parents[1]


def channel():
    return "main" if settings.get("update_channel") == "main" else "release"


def _ver(tag):
    """'v0.7.0' / '0.7.0-beta' -> (0, 7, 0); unparsable -> ()."""
    m = re.match(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(tag).strip())
    return tuple(int(x or 0) for x in m.groups()) if m else ()


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "LoRA-Studio"})
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.loads(r.read().decode("utf-8"))


def _fetch_release():
    rel = [x for x in _get(RELEASES) if not x.get("draft") and _ver(x.get("tag_name"))]
    rel.sort(key=lambda x: _ver(x["tag_name"]), reverse=True)
    if not rel:
        return None
    x = rel[0]
    return {"tag": x["tag_name"], "url": x.get("html_url"), "name": x.get("name") or x["tag_name"],
            "prerelease": bool(x.get("prerelease")), "published": x.get("published_at")}


def _fetch_main():
    x = _get(MAIN)
    sha = x["sha"]
    c = x.get("commit") or {}
    return {"tag": f"main ({sha[:7]})", "sha": sha, "url": x.get("html_url"), "channel": "main",
            "name": (c.get("message") or "").splitlines()[0] if c.get("message") else sha[:7],
            "published": (c.get("committer") or {}).get("date")}


def _git(*args):
    if not (ROOT / ".git").exists() or not shutil.which("git"):
        return None
    try:
        p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=15,
                           creationflags=CREATE_NO_WINDOW)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


def _when(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def installed_commit_file():
    """Where a zip install remembers which main commit it was updated to."""
    return paths.data_dir() / "installed_commit.json"


def _main_is_newer(latest):
    head = _git("rev-parse", "HEAD")
    if head:                                       # a git folder: compare with what's checked out
        if head == latest["sha"]:
            return False
        local, remote = _when(_git("log", "-1", "--format=%cI", "HEAD")), _when(latest.get("published"))
        return bool(local and remote and remote > local)
    rec = read_json(installed_commit_file(), {}) or {}
    return rec.get("sha") != latest["sha"]         # a zip install: newer unless we updated to this commit


def check(force=False):
    ch = channel()
    cache_file = paths.cache_dir() / "app_update.json"
    cache = read_json(cache_file, {}) or {}
    latest = cache.get("latest") if cache.get("channel", "release") == ch else None
    if force or latest is None or time.time() - (cache.get("checked") or 0) > EVERY:
        try:
            latest = _fetch_main() if ch == "main" else _fetch_release()
            write_json(cache_file, {"checked": time.time(), "channel": ch, "latest": latest})
        except Exception:
            pass   # offline or GitHub busy: just use what we knew
    if not latest:
        newer = False
    elif ch == "main":
        newer = _main_is_newer(latest)
    else:
        newer = _ver(latest["tag"]) > _ver(__version__)
    return {"current": __version__, "latest": latest, "newer": newer, "channel": ch}
