"""Writes the release notes (used by .github/workflows/release.yml).

The notes come from each pull request's "Release notes" section, e.g.

    ## Release notes
    **Notifications stay out of the way.** They now stack into one small card...

Any heading containing "release notes" works ("## Suggested release notes (v1.3.0)" too), and
"> " quote markers are removed. The section runs to the end of the description (or a --- divider),
so keep it last; it can have its own headings. Without that section a pull request is listed by its title.

Roll-up: pull requests merged without bumping the version don't get a release of their own. The next
release collects them: its notes are the merged pull request's notes first, then every pull request
merged since the last release, newest first. A manual run (Actions > Release > Run workflow) does the
same without a "current" pull request. If none of them has notes, docs/release-notes/<version>.md is
used when it exists.

Usage:
    python .github/release_notes.py --version     print the version in studio/__init__.py
    python .github/release_notes.py OUT_FILE      write the notes; reads PR_TITLE, PR_BODY, PR_NUMBER
                                                  (empty on a manual run), APP_NAME, GITHUB_REPOSITORY, GH_TOKEN
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version():
    m = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "studio" / "__init__.py").read_text(encoding="utf-8"))
    return m.group(1)


def notes_section(body):
    """The text under the first heading that mentions release notes, to the end of the description
    (or a --- divider), so the notes can have their own headings like "## ✨ New". Keep the
    Release notes section last in the PR. None if there's no such heading or it's empty."""
    lines = (body or "").replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^#{1,6}\s+(.*)$", line.strip())
        if m and "release notes" in m.group(1).lower():
            lines = lines[i + 1:]
            break
    else:
        return None
    out = []
    for line in lines:
        if re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", line):
            break  # a divider ends the notes (footers, signatures)
        if line.lstrip().startswith("<!--") and line.rstrip().endswith("-->"):
            continue  # template hints
        out.append(re.sub(r"^\s*>\s?", "", line))
    text = "\n".join(out).strip()
    return text or None


def build(title, body, number, earlier=(), fallback=None, app="", ver=""):
    """Notes for the merged pull request (title/body/number; all empty on a manual run), followed by
    `earlier`: pull requests merged since the last release, newest first, as GitHub API dicts."""
    prs = ([{"title": title, "body": body, "number": number}] if (title or number) else []) + list(earlier)
    sections = [notes_section(p.get("body")) for p in prs]
    if not any(sections) and fallback:
        text = fallback.strip()
    elif prs:
        text = "\n\n".join(s or f"- {(p.get('title') or '').strip()}" for p, s in zip(prs, sections))
    else:
        text = f"{app} {ver}".strip()
    numbers = [f"#{p['number']}" for p in prs if p.get("number")]
    if numbers:
        text += f"\n\n<sub>From {', '.join(numbers)}</sub>"
    return text + "\n"


# ---- the pull requests merged since the last release (GitHub REST API) ----

def _get(path):
    req = urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}",
                                 headers={"Accept": "application/vnd.github+json",
                                          "Authorization": f"Bearer {os.environ['GH_TOKEN']}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def merged_since_last_release(skip=None):
    """Pull requests into main merged after the newest release, newest first. None released yet: []."""
    latest = _get("/releases/latest")
    if not latest:
        return []
    since = latest.get("published_at") or latest["created_at"]
    found = []
    for page in range(1, 11):
        items = _get(f"/pulls?state=closed&base=main&sort=updated&direction=desc&per_page=100&page={page}") or []
        found += [p for p in items if p.get("merged_at") and p["merged_at"] > since and str(p["number"]) != str(skip)]
        if len(items) < 100 or items[-1]["updated_at"] <= since:
            break   # sorted by last update, so older pages can't hold anything merged after the release
    return sorted(found, key=lambda p: p["merged_at"], reverse=True)


if __name__ == "__main__":
    if sys.argv[1] == "--version":
        print(version())
        sys.exit()
    v = version()
    number = os.environ.get("PR_NUMBER", "")
    earlier = merged_since_last_release(skip=number) if os.environ.get("GH_TOKEN") else []
    doc = ROOT / "docs" / "release-notes" / f"{v}.md"
    Path(sys.argv[1]).write_text(
        build(os.environ.get("PR_TITLE", ""), os.environ.get("PR_BODY", ""), number, earlier,
              fallback=doc.read_text(encoding="utf-8") if doc.is_file() else None,
              app=os.environ.get("APP_NAME", ""), ver=v),
        encoding="utf-8")
