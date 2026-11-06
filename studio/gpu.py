"""GPU stats from nvidia-smi (comes with the NVIDIA driver)."""
import shutil

from .util import run

FIELDS = ["index", "name", "memory.used", "memory.total", "utilization.gpu", "temperature.gpu", "power.draw", "power.limit"]


def stats():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"available": False, "reason": "nvidia-smi wasn't found (it comes with NVIDIA's driver)."}
    code, out = run([exe, f"--query-gpu={','.join(FIELDS)}", "--format=csv,noheader,nounits"], timeout=5)
    if code != 0:
        return {"available": False, "reason": out.strip()[-200:]}
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != len(FIELDS):
            continue
        d = dict(zip(FIELDS, parts))

        def num(k):
            try:
                return float(d[k])
            except ValueError:
                return None
        gpus.append({"index": int(num("index") or 0), "name": d["name"],
                     "mem_used": num("memory.used"), "mem_total": num("memory.total"),
                     "util": num("utilization.gpu"), "temp": num("temperature.gpu"),
                     "power": num("power.draw"), "power_limit": num("power.limit")})
    return {"available": bool(gpus), "gpus": gpus}
