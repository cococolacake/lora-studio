"""Thumbnails (cached on disk) for the image grids."""
import hashlib
import io
import os

from PIL import Image, ImageOps

from . import paths


def thumbnail_bytes(path, size=256):
    st = os.stat(path)
    key = hashlib.sha1(f"{os.path.abspath(path)}|{st.st_mtime_ns}|{st.st_size}|{size}".encode()).hexdigest()
    cache = paths.sub("cache/thumbs") / f"{key}.jpg"
    if cache.exists():
        return cache.read_bytes()
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((size, size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=86)
    data = buf.getvalue()
    try:
        cache.write_bytes(data)
    except OSError:
        pass
    return data
