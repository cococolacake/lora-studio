"""gallery-dl inside LoRA Studio: install it, store site logins, download a search or page into a folder.

gallery-dl is installed into LoRA Studio's own environment (not sd-scripts'). Site logins live in
<data folder>/gallery-dl.json, which is passed with --config; your own gallery-dl config still applies too.
"""
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus

from . import paths
from .dataset_tools import METADATA
from .util import Task, is_image, read_json, run, write_json

SITES = {
    "danbooru": {"label": "Danbooru", "fields": [("username", "Username"), ("password", "API key")],
                 "help": "Optional. Danbooru → My Account → API Key. Raises the search limits."},
    "gelbooru": {"label": "Gelbooru", "fields": [("user-id", "User ID"), ("api-key", "API key")],
                 "help": "Gelbooru → My Account → Options → API Access Credentials."},
    "e621": {"label": "e621", "fields": [("username", "Username"), ("password", "API key")],
             "help": "e621 → Account → Manage API Access."},
    "pixiv": {"label": "pixiv", "fields": [("refresh-token", "Refresh token")],
              "help": "Press “Get token”: a window opens and walks you through logging in. Paste the token it prints here."},
}

SEARCH_URLS = {
    "danbooru": "https://danbooru.donmai.us/posts?tags={tags}",
    "gelbooru": "https://gelbooru.com/index.php?page=post&s=list&tags={tags}",
    "safebooru": "https://safebooru.org/index.php?page=post&s=list&tags={tags}",
    "e621": "https://e621.net/posts?tags={tags}",
}


def _py():
    """The console Python (python.exe), even when LoRA Studio itself runs windowless via pythonw.exe."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return sys.executable


def _conf_path():
    return paths.data_dir() / "gallery-dl.json"


def installed():
    code, out = run([_py(), "-m", "gallery_dl", "--version"], timeout=30)
    return {"installed": code == 0, "version": out.strip() if code == 0 else ""}


def install():
    def go(task):
        if task.stream([_py(), "-m", "pip", "install", "--upgrade", "gallery-dl"]) != 0:
            task.finish(False)
    return Task.spawn("Installing gallery-dl", go)


def get_accounts():
    """Which sites have logins saved (values masked: they're secrets)."""
    conf = read_json(_conf_path(), {}) or {}
    ext = conf.get("extractor", {})
    out = {}
    for site, meta in SITES.items():
        vals = ext.get(site, {})
        out[site] = {k: ("•" * 8 if vals.get(k) else "") for k, _ in meta["fields"]}
    out["cookies_browser"] = ext.get("cookies-from-browser-choice", "")
    return {"sites": SITES, "values": out}


def save_account(site, values):
    if site not in SITES:
        raise RuntimeError("Unknown site.")
    conf = read_json(_conf_path(), {}) or {}
    ext = conf.setdefault("extractor", {})
    cur = ext.setdefault(site, {})
    for k, _ in SITES[site]["fields"]:
        v = (values.get(k) or "").strip()
        if v and set(v) != {"•"}:      # unchanged masked value: keep what's stored
            cur[k] = v
        elif not v:
            cur.pop(k, None)
    if not cur:
        ext.pop(site, None)
    write_json(_conf_path(), conf)
    return get_accounts()


def set_cookies_browser(browser):
    conf = read_json(_conf_path(), {}) or {}
    ext = conf.setdefault("extractor", {})
    if browser:
        ext["cookies-from-browser-choice"] = browser
    else:
        ext.pop("cookies-from-browser-choice", None)
    write_json(_conf_path(), conf)
    return get_accounts()


def pixiv_token_window():
    """Open a console running 'gallery-dl oauth:pixiv' so the user can log in and copy the token."""
    cmd = [_py(), "-m", "gallery_dl", "oauth:pixiv"]
    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/k", *cmd], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True
    term = open_terminal(cmd)
    if not term:
        raise RuntimeError("Couldn't find a terminal app to open. Run this in a terminal instead, "
                           "then paste the token here:  " + " ".join(shlex.quote(c) for c in cmd))
    return True


# Terminal apps to try on Linux, with how each wants the command passed.
TERMINALS = [
    ("x-terminal-emulator", ["-e"]),
    ("gnome-terminal", ["--"]),
    ("konsole", ["-e"]),
    ("xfce4-terminal", ["-x"]),
    ("kitty", []),
    ("alacritty", ["-e"]),
    ("xterm", ["-e"]),
]


def open_terminal(cmd):
    """Run cmd in a new terminal window, keeping it open afterwards so the output can be read."""
    keep_open = ["bash", "-c", " ".join(shlex.quote(c) for c in cmd) + "; echo; read -p 'Press Enter to close.'"]
    for name, flag in TERMINALS:
        exe = shutil.which(name)
        if exe:
            subprocess.Popen([exe, *flag, *keep_open], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return name
    return None


def build_url(site, tags):
    tags = " ".join((tags or "").split())
    if site not in SEARCH_URLS or not tags:
        raise RuntimeError("Pick a site and enter some tags.")
    return SEARCH_URLS[site].format(tags=quote_plus(tags))


def download(task, url, dest, limit=None, images_only=True):
    """Download into exactly <dest> (no sub-folders), with metadata files for captions."""
    if not installed()["installed"]:
        raise RuntimeError("gallery-dl isn't installed yet.")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    conf = read_json(_conf_path(), {}) or {}
    cmd = [_py(), "-m", "gallery_dl", "-D", str(dest), "--write-metadata", "--no-part"]
    if _conf_path().exists():
        cmd += ["-c", str(_conf_path())]
    browser = (conf.get("extractor") or {}).get("cookies-from-browser-choice")
    if browser:
        cmd += ["--cookies-from-browser", browser]
    if limit:
        cmd += ["--range", f"1-{int(limit)}"]
    if images_only:
        cmd += ["--filter", "extension in ('jpg', 'jpeg', 'png', 'webp', 'bmp')"]
    cmd.append(url)
    total = int(limit) if limit else None
    count = {"n": 0}
    file_re = re.compile(r"\.(jpe?g|png|webp|bmp|gif)\s*$", re.I)

    def on_line(line):
        s = line.strip()
        if s.startswith("#"):          # already downloaded before
            s = s[1:].strip()
        if file_re.search(s) and ("/" in s or "\\" in s):
            count["n"] += 1
            task.progress = {"n": count["n"], "total": total or count["n"], "msg": f"Downloaded {count['n']}{f' of {total}' if total else ''}"}
            return True
        return False

    task.progress = {"n": 0, "total": total or 1, "msg": "Starting gallery-dl…"}
    code = task.stream(cmd, on_line=on_line)
    if count["n"] == 0:
        task.log("Nothing was downloaded. Check the URL or tags, and whether the site needs a login.")
        raise RuntimeError("gallery-dl didn't download anything.")
    if code != 0:
        task.log(f"gallery-dl finished with warnings (exit code {code}); keeping what was downloaded.")
    task.log(f"Downloaded {count['n']} files into {dest}.")
    moved = tidy_metadata(dest)
    if moved:
        task.log(f"Moved {moved} metadata files (tags used for captions) into the {METADATA} folder.")
    return {"downloaded": count["n"], "dest": str(dest).replace("\\", "/")}


def tidy_metadata(folder):
    """Move gallery-dl's image.jpg.json files out of the way, into <folder>/_metadata.
    They hold each image's tags, which the New dataset step turns into captions."""
    folder = Path(folder)
    meta = folder / METADATA
    n = 0
    for f in list(folder.glob("*.json")):
        if not is_image(f.stem):         # only "<image name>.json", never other files
            continue
        meta.mkdir(exist_ok=True)
        target = meta / f.name
        if target.exists():
            target.unlink()
        shutil.move(str(f), str(target))
        n += 1
    return n


def default_download_dir(name):
    safe = re.sub(r"[^\w\- ]+", "_", name).strip() or "download"
    return str(paths.sub("downloads") / safe).replace("\\", "/")

