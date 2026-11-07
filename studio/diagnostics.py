"""A short, paste-ready report for bug reports ("Copy diagnostics").

Everything personal is left out or masked: your home folder shows as ~, and site logins,
API keys and the like are never included.
"""
import os
import platform
import sys
from pathlib import Path

from . import __version__, gpu, runs, sdscripts, settings, trainer


def _mask(text):
    """Hide the home folder (it usually contains your name), e.g. C:/Users/you -> ~."""
    s = str(text)
    home = str(Path.home())
    for h in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
        if h and len(h) > 3:
            s = s.replace(h, "~")
    return s


def _os_name():
    if os.name == "nt":
        return f"Windows {platform.release()} ({platform.version()})"
    try:
        import distro  # optional
        return f"{distro.name(pretty=True)}"
    except Exception:
        pass
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return f"{platform.system()} {platform.release()}"


def report(native=None):
    lines = ["### LoRA Studio diagnostics", ""]
    add = lambda k, v: lines.append(f"- **{k}:** {v}")
    add("LoRA Studio", __version__)
    add("System", _os_name())
    add("Python (app)", platform.python_version())
    if native is not None:
        add("Window", "app window" if native else "browser mode")

    try:
        st = sdscripts.status()
    except Exception as e:
        st = {"error": str(e)}
    if not st.get("configured"):
        add("sd-scripts", "not set up")
    elif not st.get("valid", True):
        add("sd-scripts", "folder set, but it doesn't look like sd-scripts")
    else:
        bits = [st.get("branch") or "?", st.get("commit") or "?"]
        if st.get("commit_age"):
            bits.append(f"({st['commit_age']})")
        add("sd-scripts", " ".join(bits) + ("" if st.get("venv") else " · no venv found"))
        add("Launcher", settings.get("launcher"))

    try:
        g = gpu.stats()
        if g.get("available"):
            for x in g.get("gpus", []):
                mem = f"{(x.get('mem_total') or 0) / 1024:.0f} GB" if x.get("mem_total") else "?"
                add(f"GPU {x.get('index', 0)}", f"{x.get('name')} ({mem})" + (f", driver {g['driver']}" if g.get("driver") else ""))
        else:
            add("GPU", g.get("reason") or "not available")
    except Exception as e:
        add("GPU", f"couldn't read ({e})")

    # The most recent run that didn't finish well, with the end of its log.
    try:
        bad = next((r for r in runs.list_runs() if r.get("status") in ("failed", "error", "interrupted")), None)
    except Exception:
        bad = None
    if bad:
        lines += ["", f"**Last problem run:** {bad.get('script')} · {bad.get('status')}"]
        try:
            log = runs.log(bad["id"]).get("lines", [])[-40:]
        except Exception:
            log = []
        if log:
            lines += ["", "```", *[_mask(l) for l in log], "```"]
    return _mask("\n".join(lines))
