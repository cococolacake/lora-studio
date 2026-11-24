"""Datasets: building a dataset from a download, tidying tags, character tags and linked images."""
import json
import os

import pytest
from PIL import Image

from helpers import img
from studio import gallerydl, importer
from studio.util import Task


def test_build_in_place_keeps_captions_and_bins_small_images(tmp_path):
    d = tmp_path / "ds"
    (d / "_metadata").mkdir(parents=True)
    img(d / "DATA_1.png"); (d / "DATA_1.txt").write_text("old caption")
    img(d / "a.jpg"); (d / "_metadata" / "a.jpg.json").write_text(json.dumps({"tags": ["blue", "sky"]}))
    img(d / "tiny.png", (64, 64))
    r = importer.run(Task("t"), {"source": str(d), "dest": str(d), "min_side": 256})
    assert r["copied"] == 2 and r["too_small"] == 1
    caps = sorted(f.read_text() for f in d.glob("*.txt"))
    assert caps == ["blue, sky", "old caption"]
    assert (d / "_deleted" / "tiny.png").exists()


def test_dataset_only_uses_this_downloads_files(tmp_path):
    dl = tmp_path / "dl"; dl.mkdir()
    for n in ("old1.png", "old2.png", "new1.png"):
        img(dl / n)
    r = importer.run(Task("t"), {"source": str(dl), "dest": str(tmp_path / "ds"), "min_side": 64,
                                 "files": [str(dl / "new1.png")]})
    assert r["copied"] == 1


def test_build_in_place_refuses_to_mix_downloads(tmp_path):
    dl = tmp_path / "dl"; dl.mkdir()
    img(dl / "other_artist.png"); img(dl / "mine.png")
    with pytest.raises(RuntimeError, match="another download"):
        importer.run(Task("t"), {"source": str(dl), "dest": str(dl), "min_side": 64, "files": [str(dl / "mine.png")]})


def test_tidy_metadata(tmp_path):
    img(tmp_path / "1.png"); (tmp_path / "1.png.json").write_text("{}"); (tmp_path / "settings.json").write_text("{}")
    assert gallerydl.tidy_metadata(tmp_path) == 1
    assert (tmp_path / "_metadata" / "1.png.json").exists() and (tmp_path / "settings.json").exists()


def test_download_folder_named_after_link():
    assert gallerydl.name_from_url("https://www.pixiv.net/en/users/74156805/artworks") == "pixiv users 74156805"


def test_character_tags_sorts_fixed_look_from_what_changes():
    from studio.dataset_tools import classify_tag
    fixed = {"long hair": "hair", "hair between eyes": "hair", "blue eyes": "eyes", "cat ears": "body",
             "white thighhighs": "outfit", "hair ornament": "outfit", "school uniform": "outfit"}
    for tag, group in fixed.items():
        assert classify_tag(tag) == group, tag
    for tag in ["smile", "closed eyes", "hand in own hair", "holding hat", "skirt lift", "sitting",
                "simple background", "looking at viewer", "open jacket", "1girl", "sword"]:
        assert classify_tag(tag) is None, tag


def test_character_tag_prune_is_one_undo(tmp_path):
    from PIL import Image
    from studio import dataset_tools as dt
    caps = ["1girl, long hair, blue eyes, smile, red dress",
            "1girl, long_hair, blue eyes, sitting, red dress, hat",
            "mychar, 1girl, long hair, blue eyes, closed eyes"]
    for i, c in enumerate(caps):
        Image.new("RGB", (8, 8)).save(tmp_path / f"{i}.png")
        (tmp_path / f"{i}.txt").write_text(c, encoding="utf-8")
    found = dt.character_tags(str(tmp_path), "mychar")
    counts = {t["tag"]: (t["count"], t["group"]) for t in found["tags"]}
    assert found["total"] == 3
    assert counts["long hair"] == (3, "hair") and counts["red dress"] == (2, "outfit") and counts["hat"] == (1, "outfit")
    assert "smile" not in counts and "closed eyes" not in counts and "mychar" not in counts

    r = dt.bulk(str(tmp_path), "prune", {"tags": "long hair, blue eyes, red dress", "trigger": "mychar"})
    assert r["changed"] == 3
    assert (tmp_path / "1.txt").read_text(encoding="utf-8") == "mychar, 1girl, sitting, hat"
    assert (tmp_path / "2.txt").read_text(encoding="utf-8") == "mychar, 1girl, closed eyes"
    dt.undo(str(tmp_path))
    assert [(tmp_path / f"{i}.txt").read_text(encoding="utf-8") for i in range(3)] == caps


def test_dataset_images_link_to_downloads_and_edits_never_touch_them(tmp_path):
    from studio import dataset_tools as dt
    dl, ds = tmp_path / "downloads", tmp_path / "dataset"
    dl.mkdir()
    Image.new("RGB", (800, 600), (200, 100, 150)).save(dl / "post_1.png")
    out = importer.run(Task("t"), {"source": str(dl), "dest": str(ds), "min_side": 0, "captions": "none"})
    img = ds / "DATA_1.png"
    assert out["copied"] == 1 and img.exists()
    if out["linked"]:   # hard links work here: same file, no extra space
        assert os.stat(img).st_ino == os.stat(dl / "post_1.png").st_ino
    dt.crop_image(str(img), [0, 0, 400, 300])
    with Image.open(dl / "post_1.png") as im:
        assert im.size == (800, 600)          # the download is untouched
    with Image.open(img) as im:
        assert im.size == (400, 300)
    dt.restore_original(str(img))
    with Image.open(img) as im:
        assert im.size == (800, 600)
    assert not list(ds.glob("*.tmp"))
