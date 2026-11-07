"""'When the queue is done': sleep or shut down the PC after the last training.

One-time and safe: after the queue empties there's a 60-second countdown that can be cancelled
from LoRA Studio, and the choice goes back to "Do nothing" once it has been used.
"""
import os
import shutil
import subprocess
import threading
import time

from .util import CREATE_NO_WINDOW

GRACE = 60   # seconds between "queue finished" and actually sleeping/shutting down

ACTIONS = ("none", "sleep", "shutdown")
_lock = threading.Lock()
_state = {"action": "none", "pending": None, "until": None}
_timer = None


def get():
    with _lock:
        left = max(0, int(_state["until"] - time.time())) if _state["until"] else None
        return {"action": _state["action"], "pending": _state["pending"], "seconds_left": left}


def set_action(action):
    if action not in ACTIONS:
        raise RuntimeError(f"Unknown choice {action}.")
    with _lock:
        _state["action"] = action
    return get()


def cancel():
    global _timer
    with _lock:
        if _timer:
            _timer.cancel()
            _timer = None
        _state.update(pending=None, until=None, action="none")
    return get()


def queue_finished():
    """Called when the last queued training has ended (not when the user pressed Stop)."""
    global _timer
    with _lock:
        action = _state["action"]
        if action == "none" or _state["pending"]:
            return
        _state.update(pending=action, until=time.time() + GRACE)
        _timer = threading.Timer(GRACE, _go, args=(action,))
        _timer.daemon = True
        _timer.start()
    from . import notify
    verb = "go to sleep" if action == "sleep" else "shut down"
    notify.toast("Training queue finished", f"Your PC will {verb} in 1 minute. Open LoRA Studio to cancel.")


def _go(action):
    global _timer
    with _lock:
        if _state["pending"] != action:
            return   # cancelled in the meantime
        _state.update(pending=None, until=None, action="none")
        _timer = None
    try:
        _run(action)
    except Exception:
        pass


def _run(action):
    if os.name == "nt":
        if action == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", "0"], creationflags=CREATE_NO_WINDOW)
        else:   # real sleep (not hibernate), via Windows' own power API
            ps = ("Add-Type -AssemblyName System.Windows.Forms; "
                  "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)")
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], creationflags=CREATE_NO_WINDOW)
    else:
        cmd = "suspend" if action == "sleep" else "poweroff"
        if shutil.which("systemctl"):
            subprocess.Popen(["systemctl", cmd])
