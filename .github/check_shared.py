"""Checks that the files this app shares with its sister app still match the sister app's copy.

Some files are the same in both apps (the theme engine's colours, CSS themes, the API bridge, the
release and wiki workflows...). When one changes, the other usually should too. This compares each
one with the other app's `main` branch on GitHub, after swapping the app names, and prints a
warning for each that differs. It never fails the checks: a change often lands in one app first.

The other app's repository name isn't written anywhere in this repo. The Checks workflow reads it
from the OTHER_APP_REPO repository variable (Settings > Secrets and variables > Actions > Variables).
Without it, the check is skipped.

Usage: python .github/check_shared.py [other-repo-name]      (this file is shared too)
"""
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "cococolacake"

# {app} is each app's repository name.
SHARED = [
    ".gitattributes",
    ".github/check_shared.py",
    ".github/release_notes.py",
    ".github/workflows/wiki.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    "Install.bat",
    "{app}.sh",
    "LICENSE",
    "studio/appupdate.py",
    "studio/csstheme.py",
    "studio/gpu.py",
    "web/index.html",
    "web/css/custom.css",
    "web/css/tokens.css",
    "web/fonts/Geist-LICENSE.txt",
    "web/fonts/Geist-Variable.woff2",
    "web/fonts/GeistMono-Variable.woff2",
    "web/js/api.js",
    "web/js/csstheme.js",
]


def this_repo():
    """This app's repository name, from GitHub Actions or from the git remote."""
    full = os.environ.get("GITHUB_REPOSITORY", "")
    if not full:
        try:
            url = subprocess.run(["git", "-C", str(ROOT), "config", "--get", "remote.origin.url"],
                                 capture_output=True, text=True).stdout.strip()
        except OSError:
            url = ""
        full = re.sub(r"\.git$", "", url)
    return full.rstrip("/").split("/")[-1]


def name_pattern(repo):
    """'some-app' matches 'Some App', 'some-app', 'SOME_APP', 'Some-App' and so on."""
    words = re.split(r"[-_ ]", repo)
    return re.compile(r"[-_ ]".join(re.escape(w) for w in words), re.IGNORECASE)


def normalize(data, patterns):
    """Both apps' names become APP, so files that differ only by name match. Binary files stay as they are."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    for p in patterns:
        text = p.sub("APP", text)
    return text.replace("\r\n", "\n").encode("utf-8")


def fetch(repo, path):
    url = f"https://raw.githubusercontent.com/{OWNER}/{repo}/main/{path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    other = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OTHER_APP_REPO", "")).strip()
    if not other:
        print("::notice::Skipped the shared-files check: the OTHER_APP_REPO variable isn't set.")
        return
    me = this_repo()
    patterns = [name_pattern(me), name_pattern(other)]
    differ = []
    for p in SHARED:
        here, there = p.replace("{app}", me), p.replace("{app}", other)
        mine = (ROOT / here).read_bytes() if (ROOT / here).is_file() else None
        try:
            theirs = fetch(other, there)
        except OSError as e:
            print(f"::warning::Couldn't reach GitHub to compare shared files ({e}).")
            return
        if mine is None and theirs is None:
            continue
        if mine is None or theirs is None or normalize(mine, patterns) != normalize(theirs, patterns):
            what = ("isn't in the other app yet" if theirs is None else
                    "is in the other app but not here" if mine is None else "differs from the other app's copy")
            differ.append(here)
            print(f"::warning file={here}::{here} {what}. Shared files usually change in both apps.")
    print(f"{len(SHARED) - len(differ)} of {len(SHARED)} shared files match the other app.")


if __name__ == "__main__":
    sys.exit(main())
