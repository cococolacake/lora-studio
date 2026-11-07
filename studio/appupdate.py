"""Is there a newer LoRA Studio on GitHub? Checked at most every few hours, quietly; never blocks."""
import json
import re
import time
import urllib.request

from . import __version__, paths
from .util import read_json, write_json

REPO = "cococolacake/lora-studio"
RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=10"
EVERY = 6 * 3600


def _ver(tag):
    """'v0.7.0' / '0.7.0-beta' -> (0, 7, 0); unparsable -> ()."""
    m = re.match(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(tag).strip())
    return tuple(int(x or 0) for x in m.groups()) if m else ()


def _fetch():
    req = urllib.request.Request(RELEASES, headers={"Accept": "application/vnd.github+json", "User-Agent": "LoRA-Studio"})
    with urllib.request.urlopen(req, timeout=6) as r:
        data = json.loads(r.read().decode("utf-8"))
    rel = [x for x in data if not x.get("draft") and _ver(x.get("tag_name"))]
    rel.sort(key=lambda x: _ver(x["tag_name"]), reverse=True)
    if not rel:
        return None
    x = rel[0]
    return {"tag": x["tag_name"], "url": x.get("html_url"), "name": x.get("name") or x["tag_name"],
            "prerelease": bool(x.get("prerelease")), "published": x.get("published_at")}


def check(force=False):
    cache_file = paths.cache_dir() / "app_update.json"
    cache = read_json(cache_file, {}) or {}
    latest = cache.get("latest")
    if force or time.time() - (cache.get("checked") or 0) > EVERY:
        try:
            latest = _fetch()
            write_json(cache_file, {"checked": time.time(), "latest": latest})
        except Exception:
            pass   # offline or GitHub busy: just use what we knew
    newer = bool(latest) and _ver(latest["tag"]) > _ver(__version__)
    return {"current": __version__, "latest": latest, "newer": newer}
