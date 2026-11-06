"""Back up / restore LoRA Studio's own data: settings, presets, themes and run history."""
import time
import zipfile
from pathlib import Path

from . import paths

SKIP = {"cache", "backups", "downloads", "logs"}
SECRETS = {"gallery-dl.json"}   # site logins stay on this PC


def create(dest_folder=None):
    dest = Path(dest_folder) if dest_folder else paths.sub("backups")
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"LoRA Studio backup {time.strftime('%Y-%m-%d %H%M')}.zip"
    root = paths.data_dir()
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in root.rglob("*"):
            rel = f.relative_to(root)
            if f.is_file() and rel.parts[0] not in SKIP and not f.name.endswith(".tmp") and f.name not in SECRETS:
                z.write(f, rel.as_posix())
                count += 1
        z.writestr("LORA_STUDIO_BACKUP", "1")
    return {"path": str(out).replace("\\", "/"), "files": count, "size": out.stat().st_size}


def restore(zip_path):
    zp = Path(zip_path)
    if not zp.is_file():
        raise RuntimeError("Backup file not found.")
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        if "LORA_STUDIO_BACKUP" not in names:
            raise RuntimeError("That zip isn't a LoRA Studio backup.")
        safety = create()   # keep what's here now, just in case
        root = paths.data_dir().resolve()
        n = 0
        for name in names:
            if name == "LORA_STUDIO_BACKUP" or name.endswith("/"):
                continue
            target = (root / name).resolve()
            if root not in target.parents:     # ignore anything trying to escape the data folder
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
            n += 1
    return {"restored": n, "safety_backup": safety["path"]}
