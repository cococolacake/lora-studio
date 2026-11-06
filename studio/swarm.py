"""SwarmUI connection: detect/launch your install, copy LoRAs into it, render test grids through it.

Uses Swarm's HTTP API (POST <url>/API/<route>, JSON in/out, session_id from GetNewSession).
"""
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import settings, trainer
from .util import Task, read_json, safe_name, write_json

DEFAULT_URL = "http://127.0.0.1:7801"


def _url():
    return (settings.get("swarm_url") or DEFAULT_URL).rstrip("/")


def _dir():
    d = settings.get("swarm_dir")
    return Path(d) if d else None


# ---- install detection -----------------------------------------------------

def is_swarm(path):
    p = Path(path)
    return (p / "launch-windows.bat").exists() or (p / "launch-linux.sh").exists() or (p / "src" / "SwarmUI.csproj").exists()


def _fds_values(text, key):
    m = re.search(rf"^\s*{key}:\s*(.+)$", text, re.M)
    return [v.strip() for v in m.group(1).split(";") if v.strip()] if m else []


def lora_dir():
    """Where Swarm looks for LoRAs: an explicit setting, else Data/Settings.fds, else Models/Lora."""
    explicit = settings.get("swarm_lora_dir")
    if explicit:
        return Path(explicit)
    d = _dir()
    if not d:
        return None
    root, sub = "Models", "Lora"
    fds = d / "Data" / "Settings.fds"
    if fds.exists():
        text = fds.read_text(encoding="utf-8", errors="replace")
        root = (_fds_values(text, "ModelRoot") or [root])[0]
        sub = (_fds_values(text, "SDLoraFolder") or [sub])[0]
    rootp = Path(root) if Path(root).is_absolute() else d / root
    subp = Path(sub) if Path(sub).is_absolute() else rootp / sub
    return subp


# ---- API -----------------------------------------------------------------------

_session = {"id": None}


def _post(route, body, timeout=10):
    req = urllib.request.Request(f"{_url()}/API/{route}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def call(route, body=None, timeout=30):
    body = dict(body or {})
    for attempt in range(2):
        if not _session["id"]:
            _session["id"] = _post("GetNewSession", {}, timeout=5)["session_id"]
        body["session_id"] = _session["id"]
        res = _post(route, body, timeout)
        if res.get("error_id") == "invalid_session_id" and attempt == 0:
            _session["id"] = None
            continue
        if res.get("error"):
            raise RuntimeError(f"SwarmUI: {res['error']}")
        return res
    raise RuntimeError("SwarmUI session problem.")


def status():
    d = _dir()
    out = {"configured": bool(d), "valid": bool(d and is_swarm(d)), "path": str(d) if d else "",
           "url": _url(), "lora_dir": str(lora_dir() or ""), "running": False}
    try:
        res = _post("GetNewSession", {}, timeout=2)
        _session["id"] = res.get("session_id")
        out.update(running=True, version=res.get("version", ""))
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return out


def launch():
    d = _dir()
    if not d or not is_swarm(d):
        raise RuntimeError("Set your SwarmUI folder first.")
    if os.name == "nt":
        bat = d / "launch-windows.bat"
        # Run the .bat in its own console (minimized) so SwarmUI's log stays visible if you need it.
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7  # SW_SHOWMINNOACTIVE
        subprocess.Popen(["cmd", "/c", str(bat), "--launch_mode", "none"], cwd=str(d),
                         creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=si)
    else:
        subprocess.Popen(["bash", str(d / "launch-linux.sh"), "--launch_mode", "none"], cwd=str(d),
                         start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def list_models(subtype="Stable-Diffusion"):
    res = call("ListModels", {"path": "", "depth": 8, "subtype": subtype}, timeout=30)
    return sorted(f["name"] for f in res.get("files", []) if f.get("name"))


def refresh():
    try:
        call("TriggerRefresh", {}, timeout=60)
        return True
    except Exception:
        return False


# ---- send LoRAs to Swarm --------------------------------------------------------

def copy_run_outputs(run_id, which, base, key):
    """Copy a run's LoRA(s) into <base>/LoRA Studio/<output_name>/ and remember it under run[key]."""
    from . import runs
    run = trainer.load_run(run_id)
    outs = runs.outputs(run)
    if not outs:
        raise RuntimeError("This run has no .safetensors files yet.")
    name = (run.get("config") or {}).get("output_name") or "lora"
    if which == "final":
        final = [o for o in outs if Path(o["name"]).stem == name]
        outs = final or outs[-1:]
    elif which == "best":
        best = (run.get("best") or {}).get("path")
        if not best or not Path(best).exists():
            raise RuntimeError("Pick a best epoch first.")
        outs = [{"path": best, "name": Path(best).name}]
    if not base:
        raise RuntimeError("Set the folder first (SwarmUI & ComfyUI page).")
    dest = Path(base) / "LoRA Studio" / safe_name(name)
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for o in outs:
        shutil.copy2(o["path"], dest / o["name"])
        copied.append(str(dest / o["name"]).replace("\\", "/"))
    run.setdefault(key, {})["sent"] = copied
    trainer.save_run(run)
    return {"copied": copied, "folder": str(dest)}


def send_run(run_id, which="final"):
    """Copy a run's LoRA(s) into SwarmUI's LoRA folder and refresh its model list."""
    res = copy_run_outputs(run_id, which, lora_dir(), "swarm")
    res["refreshed"] = refresh() if status()["running"] else False
    return res


def library_in(base):
    """LoRAs LoRA Studio has copied into a folder, grouped by output name."""
    root = Path(base) / "LoRA Studio" if base else None
    out = {"folder": str(root).replace("\\", "/") if root else "", "groups": []}
    if not root or not root.is_dir():
        return out
    for d in sorted([d for d in root.iterdir() if d.is_dir()], key=lambda d: d.stat().st_mtime, reverse=True):
        files = sorted(d.glob("*.safetensors"), key=lambda f: f.name)
        if files:
            out["groups"].append({"name": d.name, "folder": str(d).replace("\\", "/"),
                                  "modified": max(f.stat().st_mtime for f in files),
                                  "files": [{"name": f.name, "path": str(f).replace("\\", "/"), "size": f.stat().st_size}
                                            for f in files]})
    return out


def library():
    return library_in(lora_dir())


# ---- leftover theme from LoRA Studio 0.3.1 (feature removed; cleanup only) ---------------

def theme_dir():
    d = _dir()
    return d / "src" / "Extensions" / "LoRAStudioTheme" if d else None


def old_theme_installed():
    d = theme_dir()
    return bool(d and d.exists())


def remove_old_theme():
    d = theme_dir()
    if d and d.exists():
        shutil.rmtree(d)
    # its compiled copy, so SwarmUI doesn't keep loading it
    built = _dir() / "src" / "bin" / "extensions" / "SwarmExtensionLoRAStudioTheme" if _dir() else None
    if built and built.exists():
        shutil.rmtree(built, ignore_errors=True)
    return True


# ---- test grids -------------------------------------------------------------------

def _swarm_lora_names(paths):
    """Map copied files to the names Swarm uses for them."""
    try:
        names = list_models("LoRA")
    except Exception:
        names = []
    out = []
    for p in paths:
        stem = Path(p).stem
        match = next((n for n in names if Path(n).stem == stem and "LoRA Studio" in n), None)
        out.append(match or f"LoRA Studio/{Path(p).parent.name}/{stem}")
    return out


def render_grid(task, run_id, params):
    """params: model, prompts[list], files[list of copied lora paths], strengths[list], width, height,
    steps, cfg, seed, negative."""
    run = trainer.load_run(run_id)
    files = params.get("files") or (run.get("swarm") or {}).get("sent") or []
    if not files:
        raise RuntimeError("Send this run's LoRAs to SwarmUI first.")
    if not status()["running"]:
        raise RuntimeError("SwarmUI isn't running. Start it from Settings → SwarmUI (or the button here).")
    refresh()
    loras = _swarm_lora_names(files)
    strengths = [float(s) for s in params.get("strengths") or [1.0]]
    prompts = [p for p in params.get("prompts") or [] if p.strip()]
    if not prompts:
        raise RuntimeError("Add at least one prompt.")
    out_dir = trainer.run_dir(run_id) / "swarm"
    out_dir.mkdir(exist_ok=True)
    grid = {"params": params, "loras": loras, "strengths": strengths, "prompts": prompts, "cells": [],
            "started": time.time()}
    total = len(loras) * len(strengths) * len(prompts)
    n = 0
    for li, lora in enumerate(loras):
        for si, w in enumerate(strengths):
            for pi, prompt in enumerate(prompts):
                n += 1
                task.progress = {"n": n - 1, "total": total, "msg": f"{Path(lora).name} @ {w} · prompt {pi + 1}"}
                body = {"images": 1, "prompt": prompt, "negativeprompt": params.get("negative", ""),
                        "model": params["model"], "width": int(params.get("width", 1024)),
                        "height": int(params.get("height", 1024)), "steps": int(params.get("steps", 28)),
                        "cfgscale": float(params.get("cfg", 5)), "seed": int(params.get("seed", 42)),
                        "loras": lora, "loraweights": str(w)}
                try:
                    res = call("GenerateText2Image", body, timeout=900)
                    img = (res.get("images") or [None])[0]
                    if not img:
                        raise RuntimeError("no image returned")
                    dest = out_dir / f"l{li:02d}_s{si:02d}_p{pi:02d}.png"
                    if img.startswith("data:"):
                        import base64
                        dest.write_bytes(base64.b64decode(img.split(",", 1)[1]))
                    else:
                        with urllib.request.urlopen(f"{_url()}/{img.lstrip('/')}", timeout=60) as r:
                            dest.write_bytes(r.read())
                    grid["cells"].append({"l": li, "s": si, "p": pi, "path": str(dest).replace("\\", "/")})
                    task.log(f"✓ {Path(lora).name} @ {w} · prompt {pi + 1}")
                except Exception as e:
                    task.log(f"✗ {Path(lora).name} @ {w} · prompt {pi + 1}: {e}")
                    grid["cells"].append({"l": li, "s": si, "p": pi, "error": str(e)})
                write_json(trainer.run_dir(run_id) / "swarm_grid.json", grid)
    task.progress = {"n": total, "total": total, "msg": "Done"}
    return {"cells": len(grid["cells"])}


def start_grid(run_id, params):
    return Task.spawn("Rendering test grid in SwarmUI", render_grid, run_id, params)


def grid(run_id):
    return read_json(trainer.run_dir(run_id) / "swarm_grid.json")
