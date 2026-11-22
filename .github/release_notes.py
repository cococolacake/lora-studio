"""Writes the release notes for a merged pull request (used by .github/workflows/release.yml).

The notes come from the pull request's "Release notes" section, e.g.

    ## Release notes
    **Notifications stay out of the way.** They now stack into one small card...

Any heading containing "release notes" works ("## Suggested release notes (v1.3.0)" too), and
"> " quote markers are removed. The section runs to the end of the description (or a --- divider),
so keep it last; it can have its own headings. Without that section the notes fall back to the PR's title.

Usage: python .github/release_notes.py OUT_FILE   (reads PR_TITLE, PR_BODY, PR_NUMBER from the
environment) — prints the version from studio/__init__.py.
"""
import os
import re
import sys
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


def build(title, body, number):
    text = notes_section(body) or f"- {title.strip()}"
    if number:
        text += f"\n\n<sub>From #{number}</sub>"
    return text + "\n"


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(build(os.environ.get("PR_TITLE", ""), os.environ.get("PR_BODY", ""),
                                       os.environ.get("PR_NUMBER", "")), encoding="utf-8")
    print(version())
