"""Everything the web UI can call. Exposed to JavaScript as window.pywebview.api.<method>
(and over HTTP by devserver.py when running in a normal browser)."""
import base64
import os
import sys
import mimetypes
from pathlib import Path

import secrets

from . import (__version__, backup, comfy, dataset_tools, estimate, gallerydl, gpu, importer, notify, families, health, metadata, paths, runs, sdscripts, settings, swarm,
               tomlio, trainer, worker_run)
from .util import Task, open_in_explorer, read_json, safe_name, write_json


class Api:
    def __init__(self):
        self._window = None
        self._trainer = trainer.get()
        self._media_token = secrets.token_urlsafe(16)
        self._media_base = ""

    def _attach_window(self, window):
        self._window = window

    # ---- app / settings --------------------------------------------------

    def bootstrap(self):
        return {
            "version": __version__,
            "platform": "windows" if os.name == "nt" else ("mac" if sys.platform == "darwin" else "linux"),
            "settings": settings.load(),
            "themes": settings.list_themes(),
            "sd": sdscripts.status(),
            "scripts": sdscripts.list_scripts(),
            "guesses": sdscripts.guess_locations(),
            "data_dir": str(paths.data_dir()),
            "native": self._window is not None,
            "media": {"base": "", "token": self._media_token},   # the UI and images share one local server
        }

    def save_settings(self, patch):
        if "sd_scripts_dir" in patch and patch["sd_scripts_dir"]:
            patch["sd_scripts_dir"] = str(Path(patch["sd_scripts_dir"]).expanduser())
        return settings.save(patch)

    def save_theme(self, theme):
        return settings.save_theme(theme)

    def delete_theme(self, name):
        return settings.delete_theme(name)

    def check_sd_folder(self, path):
        p = Path(path).expanduser()
        return {"valid": sdscripts.is_sd_scripts(p), "venv": bool(sdscripts.venv_python(p)),
                "exists": p.exists()}

    # ---- native dialogs (return None in browser mode) ----------------------

    def _dialog(self, kind, file_types=()):
        if not self._window:
            return None
        import webview
        fd = getattr(webview, "FileDialog", None)
        dtype = {"folder": getattr(fd, "FOLDER", None) if fd else None,
                 "open": getattr(fd, "OPEN", None) if fd else None}[kind]
        if dtype is None:
            dtype = webview.FOLDER_DIALOG if kind == "folder" else webview.OPEN_DIALOG
        res = self._window.create_file_dialog(dtype, file_types=tuple(file_types))
        if not res:
            return None
        return (res[0] if isinstance(res, (list, tuple)) else res).replace("\\", "/")

    def pick_folder(self):
        return self._dialog("folder")

    def pick_file(self, kind="any"):
        types = {"image": ("Images (*.png;*.jpg;*.jpeg;*.webp;*.gif)",),
                 "toml": ("TOML (*.toml)",),
                 "zip": ("Zip files (*.zip)",),
                 "model": ("Models (*.safetensors;*.ckpt;*.pt;*.sft)", "All files (*.*)")}.get(kind, ())
        return self._dialog("open", types)

    def open_folder(self, path):
        open_in_explorer(path)
        return True

    def image_data_url(self, path):
        p = Path(path)
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()

    def thumbnail(self, path, size=160):
        return health.thumbnail(path, size)

    # ---- sd-scripts ---------------------------------------------------------

    def sd_status(self, fetch=False):
        st = sdscripts.status(fetch=fetch)
        if st.get("valid") and st.get("git"):
            st["changelog"] = sdscripts.changelog() if st.get("behind") else []
            st["recent"] = sdscripts.recent_commits()
        return st

    def sd_branches(self):
        return sdscripts.branches()

    def sd_update(self, install_deps=True):
        return Task.spawn("Updating sd-scripts", sdscripts.update, install_deps).id

    def sd_switch_branch(self, branch, install_deps=True):
        return Task.spawn(f"Switching to {branch}", sdscripts.switch_branch, branch, install_deps).id

    def sd_rollback(self, install_deps=True):
        return Task.spawn("Rolling back sd-scripts", sdscripts.rollback, install_deps).id

    def sd_install(self, dest, branch="main", python_cmd="", torch_index=""):
        return Task.spawn("Installing sd-scripts", sdscripts.install, dest, branch, python_cmd, torch_index).id

    def task(self, task_id, since=0):
        t = Task.get(task_id)
        return t.snapshot(since) if t else None

    def scripts(self):
        return sdscripts.list_scripts()

    def schema(self, script, refresh=False):
        data = sdscripts.schema(script, refresh)
        fam = next((s["family"] for s in sdscripts.list_scripts() if s["file"] == script), "")
        keys = {a["key"] for a in data["args"]}
        data["family"] = fam
        data["simple"] = [{"title": t, "keys": [k for k in ks if k in keys]}
                          for t, ks in families.SIMPLE_SECTIONS]
        data["simple"] = [s for s in data["simple"] if s["keys"]]
        data["defaults"] = families.defaults_for(fam, keys)
        data["dataset_defaults"] = families.DEFAULT_DATASET
        from . import samples
        data["sample_defaults"] = samples.DEFAULT
        return data

    # ---- training queue -----------------------------------------------------

    def enqueue(self, job, start=False):
        return self._trainer.enqueue(job, start)

    def queue_remove(self, run_id):
        self._trainer.remove(run_id)
        return self._trainer.state()

    def queue_move(self, run_id, delta):
        self._trainer.move(run_id, delta)
        return self._trainer.state()

    def queue_set_running(self, flag):
        self._trainer.set_running(flag)
        return self._trainer.state()

    def stop_current(self):
        return self._trainer.stop_current()

    def state(self):
        return self._trainer.state()

    def preview_toml(self, job):
        cfg = trainer.build_training_config(job.get("args"), job.get("schema_args", []))
        ds = trainer.build_dataset_toml(job.get("dataset", {}))
        return {"training": tomlio.dumps(cfg), "dataset": tomlio.dumps(ds)}

    # ---- runs ---------------------------------------------------------------

    def runs(self):
        return runs.list_runs()

    def run_detail(self, run_id):
        return runs.detail(run_id)

    def run_log(self, run_id, since=0):
        return runs.log(run_id, since)

    def run_metrics(self, run_id, since=0):
        return runs.metrics(run_id, since)

    def run_resume(self, run_id, state_path, start=True):
        job, _ = runs.job_from_run(run_id, resume_from=state_path)
        return self._trainer.enqueue(job, start)

    def run_rerun(self, run_id, start=False):
        job, _ = runs.job_from_run(run_id)
        job["name"] = f"{job.get('name')} (again)"
        return self._trainer.enqueue(job, start)

    def run_job(self, run_id):
        """Load a past run back into the Train form."""
        r = trainer.load_run(run_id)
        return {k: r.get(k) for k in ("name", "script", "family", "args", "dataset", "extra_args",
                                      "samples", "lora_info", "trigger", "send_to_swarm", "send_to_comfy")}

    def run_delete(self, run_id):
        runs.delete(run_id)
        return True

    # ---- presets -------------------------------------------------------------

    def presets(self):
        out = []
        for f in sorted(paths.presets_dir().glob("*.json")):
            p = read_json(f)
            if p:
                out.append({"name": p.get("preset_name") or f.stem, "script": p.get("script"),
                            "family": p.get("family")})
        return out

    def preset_save(self, name, job):
        job = dict(job, preset_name=name)
        job.pop("schema_args", None)
        write_json(paths.presets_dir() / f"{safe_name(name)}.json", job)
        return self.presets()

    def preset_load(self, name):
        return read_json(paths.presets_dir() / f"{safe_name(name)}.json")

    def preset_delete(self, name):
        (paths.presets_dir() / f"{safe_name(name)}.json").unlink(missing_ok=True)
        return self.presets()

    def import_toml(self, training_path="", dataset_path=""):
        """Read existing training.toml / dataset_config.toml files (e.g. from an older setup)."""
        out = {}
        if training_path:
            out["args"] = tomlio.load(training_path)
        if dataset_path:
            d = tomlio.load(dataset_path)
            g = d.get("general", {})
            ds0 = (d.get("datasets") or [{}])[0]
            ds = dict(families.DEFAULT_DATASET)
            for k in ("resolution", "enable_bucket", "bucket_reso_steps", "min_bucket_reso",
                      "max_bucket_reso", "caption_extension", "shuffle_caption", "keep_tokens", "flip_aug"):
                if k in g:
                    ds[k] = g[k]
                if k in ds0:
                    ds[k] = ds0[k]
            if isinstance(ds.get("resolution"), int):
                ds["resolution"] = [ds["resolution"], ds["resolution"]]
            ds["batch_size"] = ds0.get("batch_size", ds["batch_size"])
            ds["subsets"] = [{"image_dir": s.get("image_dir", ""), "num_repeats": s.get("num_repeats", 1),
                              "class_tokens": s.get("class_tokens", "")} for s in ds0.get("subsets", [])]
            out["dataset"] = ds
        return out

    # ---- dataset -------------------------------------------------------------

    def health_check(self, params):
        return health.check(params)

    # ---- dataset tools ---------------------------------------------------------

    def ds_list(self, folder, sub=None, ext=".txt"):
        return dataset_tools.list_folder(folder, ext, sub)

    def ds_save_caption(self, path, text, ext=".txt"):
        return dataset_tools.save_caption(path, text, ext)

    def ds_bulk(self, folder, op, params, paths=None, ext=".txt"):
        return dataset_tools.bulk(folder, op, params, paths, ext)

    def ds_undo(self, folder):
        return dataset_tools.undo(folder)

    def ds_move(self, paths, to_bin="_deleted", ext=".txt"):
        if to_bin not in dataset_tools.SPECIAL_DIRS:
            raise RuntimeError("Unknown folder.")
        return dataset_tools.move_images(paths, to_bin, ext)

    def ds_restore(self, paths, ext=".txt"):
        return dataset_tools.restore_images(paths, ext)

    def ds_rename_plan(self, folder, prefix="DATA_", start=1, recursive=False):
        return dataset_tools.rename_plan(folder, prefix, int(start), recursive)

    def ds_rename(self, folder, prefix="DATA_", start=1, recursive=False):
        return dataset_tools.rename_apply(folder, prefix, int(start), recursive)

    def ds_crop(self, path, box, out_w=None, out_h=None):
        return dataset_tools.crop_image(path, box, out_w, out_h)

    def ds_restore_original(self, path):
        return dataset_tools.restore_original(path)

    def ds_batch_resize(self, params):
        return dataset_tools.start_batch_resize(**params).id

    def autocomplete(self, prefix):
        return dataset_tools.autocomplete(self._ac_csv(), prefix)

    def _ac_csv(self):
        p = settings.get("autocomplete_csv")
        if p:
            return p
        found = dataset_tools.find_autocomplete_csvs(settings.get("swarm_dir"))
        return found[0] if found else ""

    def autocomplete_sources(self):
        return {"current": self._ac_csv(), "found": dataset_tools.find_autocomplete_csvs(settings.get("swarm_dir"))}

    # ---- tools that run in the sd-scripts venv -------------------------------

    def tag_images(self, params):
        return worker_run.run("Auto-tagging", "tagger", params).id

    def find_dupes(self, params):
        return worker_run.run("Looking for duplicates", "dedup", params).id

    def install_package(self, pkg):
        return worker_run.install_package(pkg).id

    def task_cancel(self, task_id):
        t = Task.get(task_id)
        if t and t.status == "running":
            t.cancel()
        return True

    # ---- LoRA metadata ---------------------------------------------------------

    def lora_meta(self, path):
        return metadata.read(path)

    def lora_meta_save(self, path, updates, thumb_image=None):
        updates = dict(updates)
        if thumb_image:
            updates["modelspec.thumbnail"] = metadata.thumbnail_from_image(thumb_image)
        return metadata.write(path, updates)

    # ---- SwarmUI ---------------------------------------------------------------

    def swarm_status(self):
        return swarm.status()

    def swarm_launch(self):
        return swarm.launch()

    def swarm_models(self, subtype="Stable-Diffusion"):
        return swarm.list_models(subtype)

    def swarm_send(self, run_id, which="final"):
        return swarm.send_run(run_id, which)

    def swarm_grid(self, run_id, params):
        return swarm.start_grid(run_id, params).id

    def swarm_library(self):
        return swarm.library()

    def swarm_old_theme(self):
        return swarm.old_theme_installed()

    def swarm_remove_old_theme(self):
        return swarm.remove_old_theme()

    # ---- ComfyUI ---------------------------------------------------------------

    def comfy_status(self):
        return comfy.status()

    def comfy_launch(self):
        return comfy.launch()

    def comfy_send(self, run_id, which="final"):
        return comfy.send_run(run_id, which)

    def comfy_library(self):
        return comfy.library()

    def comfy_open(self):
        import webbrowser
        webbrowser.open(comfy.url())
        return True

    def swarm_open(self):
        import webbrowser
        webbrowser.open(swarm._url())
        return True

    # ---- extras: GPU, estimates, best epoch, notifications -----------------------

    def gpu_stats(self):
        return gpu.stats()

    def estimate(self, job):
        return estimate.estimate(job)

    def run_set_best(self, run_id, path):
        return runs.set_best(run_id, path)

    def test_notification(self):
        ok = notify.toast("LoRA Studio", "Notifications are working (•ᴗ-)")
        if not ok:
            raise RuntimeError(notify.unavailable_reason())
        return True

    # ---- dataset bins ---------------------------------------------------------------

    def ds_bins(self, folder):
        return dataset_tools.bin_info(folder)

    def ds_empty_bin(self, folder, which):
        return dataset_tools.empty_bin(folder, which)

    # ---- import / gallery-dl ------------------------------------------------------------

    def make_dataset(self, params):
        return Task.spawn("Making a dataset", importer.make_dataset, params).id

    def gdl_status(self):
        return gallerydl.installed()

    def gdl_install(self):
        return gallerydl.install().id

    def gdl_accounts(self):
        return gallerydl.get_accounts()

    def gdl_save_account(self, site, values):
        return gallerydl.save_account(site, values)

    def gdl_set_cookies_browser(self, browser):
        return gallerydl.set_cookies_browser(browser)

    def gdl_pixiv_token(self):
        return gallerydl.pixiv_token_window()

    def gdl_build_url(self, site, tags):
        return gallerydl.build_url(site, tags)

    def gdl_default_dir(self, name):
        return gallerydl.default_download_dir(name)

    # ---- backup -----------------------------------------------------------------------

    def backup_create(self, folder=None):
        return backup.create(folder)

    def backup_restore(self, zip_path):
        return backup.restore(zip_path)
