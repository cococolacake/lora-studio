"""ComfyUI connection: either the ComfyUI built into SwarmUI, or a separate ComfyUI install.

mode "swarm":      uses <SwarmUI address>/ComfyBackendDirect/ and SwarmUI's LoRA folder.
mode "standalone": your own ComfyUI (portable or git) with its own address, launcher and models folder.
"""
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from . import settings, swarm

DEFAULT_URL = "http://127.0.0.1:8188"


def mode():
    m = settings.get("comfy_mode")
    if m in ("swarm", "standalone"):
        return m
    return "standalone" if settings.get("comfy_dir") else "swarm"


def _dir():
    d = settings.get("comfy_dir")
    return Path(d) if d else None


def _root(d):
    """The folder that holds main.py (portable builds nest it in ComfyUI/)."""
    if (d / "main.py").exists():
        return d
    if (d / "ComfyUI" / "main.py").exists():
        return d / "ComfyUI"
    return None


def is_comfy(path):
    return _root(Path(path)) is not None


def url():
    if mode() == "swarm":
        return swarm._url() + "/ComfyBackendDirect/"
    return (settings.get("comfy_url") or DEFAULT_URL).rstrip("/") + "/"


def lora_dir():
    if mode() == "swarm":
        return swarm.lora_dir()
    explicit = settings.get("comfy_lora_dir")
    if explicit:
        return Path(explicit)
    d = _dir()
    root = _root(d) if d else None
    return root / "models" / "loras" if root else None


def status():
    m = mode()
    out = {"mode": m, "url": url(), "lora_dir": str(lora_dir() or ""), "running": False}
    if m == "swarm":
        st = swarm.status()
        out.update(configured=st["configured"], valid=st["valid"], path=st["path"], running=st["running"])
        return out
    d = _dir()
    out.update(configured=bool(d), valid=bool(d and is_comfy(d)), path=str(d) if d else "")
    try:
        with urllib.request.urlopen(url() + "system_stats", timeout=2) as r:
            info = json.loads(r.read().decode("utf-8"))
        out["running"] = True
        out["version"] = (info.get("system") or {}).get("comfyui_version", "")
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return out


def launch():
    if mode() == "swarm":
        return swarm.launch()
    d = _dir()
    root = _root(d) if d else None
    if not root:
        raise RuntimeError("Set your ComfyUI folder first (the one with main.py, or the portable folder).")
    # Portable builds come with ready-made launchers; prefer the NVIDIA one.
    for bat in ("run_nvidia_gpu.bat", "run_nvidia_gpu_fast_fp16_accumulation.bat", "run_cpu.bat"):
        if (d / bat).exists() and os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 7  # minimized
            subprocess.Popen(["cmd", "/c", str(d / bat)], cwd=str(d),
                             creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=si)
            return True
    # git installs: use its venv if there is one
    py = "python"
    for cand in (root / "venv" / "Scripts" / "python.exe", root / ".venv" / "Scripts" / "python.exe",
                 root / "venv" / "bin" / "python", root / ".venv" / "bin" / "python"):
        if cand.exists():
            py = str(cand)
            break
    kw = {"creationflags": subprocess.CREATE_NEW_CONSOLE} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([py, "main.py"], cwd=str(root), **kw)
    return True


def send_run(run_id, which="final"):
    if mode() == "swarm":
        return swarm.send_run(run_id, which)
    return swarm.copy_run_outputs(run_id, which, lora_dir(), "comfy")


def library():
    return swarm.library_in(lora_dir())
