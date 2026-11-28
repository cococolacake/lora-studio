"""The app itself: updating, themes, CSS themes, the Windows helpers and the release notes."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from helpers import ROOT
from studio import appupdate
from studio.util import Task


def test_version_order():
    assert appupdate._ver("v0.10.0") > appupdate._ver("0.9.9") > appupdate._ver("v0.6.6") and appupdate._ver("junk") == ()


def _fake_install(root):
    (root / "studio").mkdir(parents=True)
    (root / "web" / "css").mkdir(parents=True)
    (root / "main.py").write_text("print('old')")
    (root / "studio" / "__init__.py").write_text('__version__ = "1.0.0"')
    (root / "web" / "css" / "custom.css").write_text("/* my own styles */")
    (root / ".venv").mkdir()
    (root / ".venv" / "keep.txt").write_text("venv")
    (root / "requirements.txt").write_text("")


def test_zip_update_keeps_venv_and_custom_css(tmp_path, monkeypatch):
    import zipfile
    from studio import selfupdate
    app = tmp_path / "app"; _fake_install(app)
    rel = tmp_path / "lora-studio-9.9.9"
    (rel / "studio").mkdir(parents=True); (rel / "web" / "css").mkdir(parents=True)
    (rel / "main.py").write_text("print('new')")
    (rel / "studio" / "__init__.py").write_text('__version__ = "9.9.9"')
    (rel / "web" / "css" / "custom.css").write_text("/* template */")
    (rel / "requirements.txt").write_text("")
    z = tmp_path / "rel.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in rel.rglob("*"):
            zf.write(f, f.relative_to(tmp_path).as_posix())
    monkeypatch.setattr(selfupdate, "ROOT", app)
    monkeypatch.setattr(selfupdate, "method", lambda: "zip")
    monkeypatch.setattr(selfupdate, "_download", lambda url, dest: Path(dest).write_bytes(z.read_bytes()))
    monkeypatch.setattr(selfupdate, "_requirements", lambda task: None)
    r = selfupdate.update(Task("u"), "v9.9.9")
    assert r["restart"] is True
    assert '9.9.9' in (app / "studio" / "__init__.py").read_text() and "new" in (app / "main.py").read_text()
    assert (app / "web" / "css" / "custom.css").read_text() == "/* my own styles */"
    assert (app / ".venv" / "keep.txt").exists()


def test_zip_update_refuses_a_wrong_download(tmp_path, monkeypatch):
    import zipfile
    from studio import selfupdate
    app = tmp_path / "app"; _fake_install(app)
    z = tmp_path / "bad.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("something/readme.txt", "not lora studio")
    monkeypatch.setattr(selfupdate, "ROOT", app)
    monkeypatch.setattr(selfupdate, "method", lambda: "zip")
    monkeypatch.setattr(selfupdate, "_download", lambda url, dest: Path(dest).write_bytes(z.read_bytes()))
    with pytest.raises(RuntimeError, match="isn't a LoRA Studio release"):
        selfupdate.update(Task("u"), "v9.9.9")
    assert "old" in (app / "main.py").read_text()


def test_git_update_pulls_and_respects_local_changes(tmp_path, monkeypatch):
    import shutil as sh
    if not sh.which("git"):
        pytest.skip("git not installed")
    from studio import selfupdate
    run = lambda *a, cwd: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
    origin = tmp_path / "origin"; origin.mkdir()
    run("init", "-q", "-b", "main", cwd=origin)
    run("config", "user.email", "t@t", cwd=origin); run("config", "user.name", "t", cwd=origin)
    (origin / "main.py").write_text("v1"); run("add", ".", cwd=origin); run("commit", "-qm", "v1", cwd=origin)
    app = tmp_path / "app"
    run("clone", "-q", str(origin), str(app), cwd=tmp_path)
    (origin / "main.py").write_text("v2"); run("commit", "-qam", "v2", cwd=origin)
    monkeypatch.setattr(selfupdate, "ROOT", app)
    monkeypatch.setattr(selfupdate, "_requirements", lambda task: None)
    assert selfupdate.method() == "git"
    assert selfupdate.update(Task("u"))["restart"] is True
    assert (app / "main.py").read_text() == "v2"
    (app / "main.py").write_text("my local edit")
    with pytest.raises(RuntimeError, match="changes of its own"):
        selfupdate.update(Task("u"))


def test_old_themes_move_to_glass(monkeypatch, tmp_path):
    """A setup from before the glass themes (classic pastels, patterned header) lands on glass Default,
    keeping light or dark mode, instead of on a theme that no longer exists."""
    from studio import paths, settings
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    (tmp_path / "settings.json").write_text('{"theme": {"name": "Cobalt Night", "base": "dark", "accent": "cobalt", "header": {"type": "pattern", "pattern": "dots"}}}')
    t = settings.load()["theme"]
    assert (t["style"], t["family"], t["base"], t["header"]["type"]) == ("glass", "default", "dark", "none")
    (tmp_path / "settings.json").write_text('{"theme": {"name": "Cool Glass", "style": "glass", "family": "cool", "base": "light"}}')
    assert settings.load()["theme"]["family"] == "cool"
    assert [x["name"] for x in settings.BUILTIN_THEMES] == ["Default", "Cool Glass", "Warm Glass", "Lilac", "Heart Glass"]
    assert settings.DEFAULT_THEME["glass"] == "efficient" and settings.DEFAULT_THEME["simpleWhileTraining"] is True


def test_dropped_css_themes(monkeypatch, tmp_path):
    """A dropped .css theme is saved in the data folder, can replace itself, and turning it off
    happens on its own when the theme in use is deleted."""
    from studio import paths, settings
    from studio.api import Api
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    api = Api()
    r = api.add_css_theme("Starry Sky.css", "body { color: pink; }")
    assert r["name"] == "Starry Sky" and [t["name"] for t in r["themes"]] == ["Starry Sky"]
    assert api.add_css_theme("../../evil.css", "x")["name"] == "evil"            # no leaving the folder
    assert (tmp_path / "css-themes" / "evil.css").exists()
    api.add_css_theme("Starry Sky.css", "body { color: lilac; }")                   # same name replaces
    assert api.css_theme("Starry Sky") == "body { color: lilac; }"
    assert api.css_theme("missing") == ""
    with pytest.raises(RuntimeError):
        api.add_css_theme("big.css", "a" * (9 * 1024 * 1024))
    settings.save({"theme": {**settings.load()["theme"], "css": "Starry Sky"}})
    assert [t["name"] for t in api.delete_css_theme("Starry Sky")] == ["evil"]
    assert settings.load()["theme"]["css"] == ""
    assert api.bootstrap()["css_themes"][0]["name"] == "evil"


def test_shortcut_helper_is_quiet_off_windows():
    from studio import winshortcut
    if os.name != "nt":
        assert winshortcut.make(start_menu=True, desktop=True) == []
    assert winshortcut.APP_ID == "LoRAStudio.App"
    assert 'SetCurrentProcessExplicitAppUserModelID("LoRAStudio.App")' in (ROOT / "main.py").read_text()


def test_titlebar_only_takes_plain_hex_colours():
    from studio.api import Api
    a = Api.__new__(Api)
    seen = []
    a._titlebar = lambda bg, text, dark: seen.append((bg, text, dark)) or True
    assert a.set_titlebar("#252D3F", "#EEF2FF", True) is True
    assert a.set_titlebar("red; drop", "#EEF2FF") is False and len(seen) == 1


def test_corners_come_from_the_theme():
    """Every corner size is a theme value, so a CSS theme can reshape the whole app (#50). Hairline rounding (1 to 3px)
    and circles stay as they are, and so do the theme cards' mockups, which show the built-in themes."""
    def fixed(value):
        return any(float(px) > 3 for px in re.findall(r"(?<![\w-])(\d+(?:\.\d+)?)px", re.sub(r"var\([^)]*\)", "", value)))
    left = []
    for name in ("app.css", "glass.css"):
        text = re.sub(r"\.theme-card \.tp \.mini[^{]*\{[^}]*\}", "", (ROOT / "web" / "css" / name).read_text(encoding="utf-8"))
        left += [f"{name}: {v.strip()}" for v in re.findall(r"border(?:-[a-z]+)*-radius:\s*([^;}]+)", text) if fixed(v)]
    for path in (ROOT / "web" / "js").rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        values = re.findall(r"""borderRadius\s*[:=]\s*["'`]([^"'`]+)""", text) + re.findall(r"""border(?:-[a-z]+)*-radius:\s*([^;"'`]+)""", text)
        left += [f"{path.name}: {v}" for v in values if fixed(v)]
    assert not left, left


def test_release_notes_come_from_the_pull_request():
    sys.path.insert(0, str(ROOT / ".github"))
    import release_notes as rn
    body = ("Intro\n\n## Testing\n- ok\n\n## Suggested release notes (v1.3.0)\n"
            "> **Character tags.** One click.\n>\n> - Undo works\n\n## ✨ New\n- More")
    assert rn.notes_section(body) == "**Character tags.** One click.\n\n- Undo works\n\n## ✨ New\n- More"
    tpl = "## Release notes\n<!-- hint -->\n**New thing.**\n"
    assert rn.notes_section(tpl) == "**New thing.**"
    assert rn.notes_section("## Release notes\n<!-- hint -->\n") is None
    assert rn.notes_section("## Release notes\nShort.\n\n---\n_footer_") == "Short."
    assert rn.build("Fix a typo", "no notes here", "7") == "- Fix a typo\n\n<sub>From #7</sub>\n"
    assert re.fullmatch(r"\d+\.\d+\.\d+", rn.version())


def test_release_notes_roll_up_unreleased_pull_requests():
    """Pull requests merged without a version bump are released with the next bump, newest first."""
    sys.path.insert(0, str(ROOT / ".github"))
    import release_notes as rn
    earlier = [{"number": 12, "title": "Quiet fix", "body": "no section"},
               {"number": 11, "title": "Big thing", "body": "## Release notes\n**Big thing.** Yay."}]
    notes = rn.build("Bump", "## Release notes\n**Newest.**", "13", earlier)
    assert notes == "**Newest.**\n\n- Quiet fix\n\n**Big thing.** Yay.\n\n<sub>From #13, #12, #11</sub>\n"
    # "None" leaves a behind-the-scenes pull request out
    assert rn.build("Bump", "## Release notes\n**Newest.**", "13", [{"number": 9, "title": "CI", "body": "## Release notes\nNone."}]) == "**Newest.**\n\n<sub>From #13</sub>\n"
    # a manual run has no pull request of its own
    assert rn.build("", "", "", earlier[1:]) == "**Big thing.** Yay.\n\n<sub>From #11</sub>\n"
    # nothing has notes, but docs/release-notes/<version>.md does
    assert rn.build("Bump", "", "13", [], fallback="## Notes\n- x\n").startswith("## Notes\n- x\n\n<sub>From #13")
    assert rn.build("", "", "", [], app="LoRA Studio", ver="1.5.0") == "LoRA Studio 1.5.0\n"


import zipfile  # noqa: E402
from studio import selfupdate  # noqa: E402


# ---- Update from: main ---------------------------------------------------------------------

def _main_commit(sha, date="2026-11-25T12:00:00Z", msg="Fix the thing\n\nMore words"):
    return {"sha": sha, "html_url": f"https://github.com/x/y/commit/{sha}",
            "commit": {"message": msg, "committer": {"date": date}}}


def test_main_check_finds_new_commits(tmp_path, monkeypatch):
    from studio import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(appupdate, "channel", lambda: "main")
    monkeypatch.setattr(appupdate, "installed_commit_file", lambda: tmp_path / "installed_commit.json")
    monkeypatch.setattr(appupdate, "_get", lambda url: _main_commit("b" * 40))
    # a git folder: the same commit is up to date; an older checkout isn't
    heads = {"rev-parse": "b" * 40, "log": "2026-11-24T12:00:00+00:00"}
    monkeypatch.setattr(appupdate, "_git", lambda *a: heads[a[0]])
    r = appupdate.check(force=True)
    assert r["channel"] == "main" and r["latest"]["tag"] == "main (bbbbbbb)" and r["latest"]["name"] == "Fix the thing"
    assert r["newer"] is False
    heads["rev-parse"] = "a" * 40
    assert appupdate.check(force=True)["newer"] is True
    heads["log"] = "2026-11-26T12:00:00+00:00"       # local commits newer than main: nothing to pull
    assert appupdate.check(force=True)["newer"] is False
    # a zip install: newer until it has been updated to that commit
    monkeypatch.setattr(appupdate, "_git", lambda *a: None)
    assert appupdate.check(force=True)["newer"] is True
    (tmp_path / "installed_commit.json").write_text('{"sha": "' + "b" * 40 + '"}')
    assert appupdate.check(force=True)["newer"] is False


def test_switching_channel_checks_again(tmp_path, monkeypatch):
    from studio import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(appupdate, "_get", lambda url: _main_commit("c" * 40) if "commits" in url else
                        [{"tag_name": "v9.9.9", "html_url": "u", "name": "9.9.9"}])
    monkeypatch.setattr(appupdate, "channel", lambda: "release")
    assert appupdate.check()["latest"]["tag"] == "v9.9.9"
    monkeypatch.setattr(appupdate, "channel", lambda: "main")
    assert appupdate.check()["latest"]["tag"] == "main (ccccccc)"   # not the cached release


def test_main_zip_update_downloads_that_commit_and_remembers_it(tmp_path, monkeypatch):
    app = tmp_path / "app"; _fake_install(app)
    src = tmp_path / ("REPO-" + "d" * 40)
    (src / "studio").mkdir(parents=True)
    (src / "main.py").write_text("print('main')")
    z = tmp_path / "main.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in src.rglob("*"):
            zf.write(f, f.relative_to(tmp_path).as_posix())
    urls = []
    monkeypatch.setattr(selfupdate, "ROOT", app)
    monkeypatch.setattr(selfupdate, "method", lambda: "zip")
    monkeypatch.setattr(selfupdate, "_requirements", lambda task: None)
    monkeypatch.setattr(selfupdate, "_download", lambda url, dest: (urls.append(url), Path(dest).write_bytes(z.read_bytes())))
    monkeypatch.setattr(appupdate, "channel", lambda: "main")
    monkeypatch.setattr(appupdate, "installed_commit_file", lambda: tmp_path / "installed_commit.json")
    monkeypatch.setattr(appupdate, "_get", lambda url: _main_commit("d" * 40))
    assert selfupdate.update(Task("u"), "main (ddddddd)")["restart"] is True
    assert urls == [f"https://github.com/{appupdate.REPO}/archive/{'d' * 40}.zip"]
    assert "main" in (app / "main.py").read_text()
    assert ('"' + "d" * 40 + '"') in (tmp_path / "installed_commit.json").read_text()


def test_main_git_update_pulls_main_only_on_main(tmp_path, monkeypatch):
    import shutil
    if not shutil.which("git"):
        pytest.skip("git not installed")
    run = lambda *a, cwd: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
    origin = tmp_path / "origin"; origin.mkdir()
    run("init", "-q", "-b", "main", cwd=origin)
    run("config", "user.email", "t@t", cwd=origin); run("config", "user.name", "t", cwd=origin)
    (origin / "main.py").write_text("v1"); run("add", ".", cwd=origin); run("commit", "-qm", "v1", cwd=origin)
    app = tmp_path / "app"
    run("clone", "-q", str(origin), str(app), cwd=tmp_path)
    (origin / "main.py").write_text("v2"); run("commit", "-qam", "v2", cwd=origin)
    monkeypatch.setattr(selfupdate, "ROOT", app)
    monkeypatch.setattr(selfupdate, "_requirements", lambda task: None)
    monkeypatch.setattr(appupdate, "channel", lambda: "main")
    assert selfupdate.update(Task("u"))["restart"] is True
    assert (app / "main.py").read_text() == "v2"
    run("switch", "-q", "-c", "my-branch", cwd=app)
    with pytest.raises(RuntimeError, match="not main"):
        selfupdate.update(Task("u"))
