"""Training queue, process runner, and live log/loss parsing.

Every queued job gets its own run folder:
    runs/<id>/run.json       what was trained, status, progress
    runs/<id>/training.toml  passed to the script as --config_file
    runs/<id>/dataset.toml   passed as --dataset_config
    runs/<id>/log.txt        full output (progress bars thinned out)
    runs/<id>/metrics.csv    step, epoch, loss, seconds since start
"""
import csv
import re
import subprocess
import threading
import time
from pathlib import Path

from . import paths, samples, sdscripts, settings, tomlio
from .util import child_env, kill_tree, new_id, popen_kwargs, read_json, split_cli_args, write_json

# tqdm: "steps:  12%|█▏   | 120/1000 [01:23<10:00,  1.44it/s, avr_loss=0.0912]"
PROGRESS_RE = re.compile(
    r"(\d+)%\|.*?\|\s*(\d+)/(\d+)\s*\[([\d:]+)<([\d:?]+),\s*([\d.?]+)\s*(it/s|s/it)?(?:,\s*(.*?))?\]")
POSTFIX_RE = re.compile(r"(\w+)=([-\d.eE+naif]+)")
EPOCH_RE = re.compile(r"\bepoch (\d+)/(\d+)", re.I)
SAVE_RE = re.compile(r"saving (?:checkpoint|model):?\s*(.+\.(?:safetensors|ckpt|pt))", re.I)
LOSS_KEYS = ("avr_loss", "loss", "current_loss")


def _clock_to_s(text):
    if "?" in text:
        return None
    parts = [int(p) for p in text.split(":")]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s



def safe_folder_name(name):
    """A folder name Windows and Linux both accept."""
    out = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name)).strip(" .")
    return out or "run"


# sd-scripts options that turn on or schedule sample images.
SAMPLE_KEYS = ("sample_prompts", "sample_every_n_epochs", "sample_every_n_steps", "sample_at_first", "sample_sampler")

class LogParser:
    """Turns sd-scripts output into structured progress."""

    def __init__(self):
        self.progress = {"step": 0, "total": 0, "percent": 0, "epoch": 0, "epochs": 0,
                         "loss": None, "speed": None, "speed_unit": "it/s", "elapsed": 0, "eta": None}
        self.checkpoints = []

    def feed(self, line):
        """Returns (is_progress_line, new_metric_point_or_None)."""
        point = None
        m = EPOCH_RE.search(line)
        if m and "%|" not in line:
            self.progress["epoch"], self.progress["epochs"] = int(m.group(1)), int(m.group(2))
        m = SAVE_RE.search(line)
        if m:
            self.checkpoints.append(m.group(1).strip())
        m = PROGRESS_RE.search(line)
        if not m:
            return False, None
        pct, step, total, elapsed, eta, speed, unit, postfix = m.groups()
        step, total = int(step), int(total)
        p = self.progress
        prev_step = p["step"]
        p.update(percent=int(pct), step=step, total=total, elapsed=_clock_to_s(elapsed),
                 eta=_clock_to_s(eta), speed_unit=unit or "it/s")
        try:
            p["speed"] = float(speed)
        except ValueError:
            p["speed"] = None
        loss = None
        if postfix:
            vals = dict(POSTFIX_RE.findall(postfix))
            for k in LOSS_KEYS:
                if k in vals:
                    try:
                        loss = float(vals[k])
                    except ValueError:
                        pass
                    break
        if loss is not None:
            p["loss"] = loss
            if step != prev_step:
                point = {"step": step, "epoch": p["epoch"], "loss": loss, "t": p["elapsed"]}
        return True, point


def trainer_reload(run_id):
    """Fields other modules may have written to run.json while we held the run in memory."""
    r = load_run(run_id) or {}
    return {k: r[k] for k in ("swarm", "comfy") if k in r}


def run_dir(run_id):
    return paths.runs_dir() / run_id


def load_run(run_id):
    return read_json(run_dir(run_id) / "run.json")


def save_run(run):
    write_json(run_dir(run["id"]) / "run.json", run)


def build_dataset_toml(ds):
    """UI dataset dict -> sd-scripts dataset_config structure."""
    general = {
        "resolution": [int(x) for x in ds.get("resolution", [1024, 1024])],
        "enable_bucket": bool(ds.get("enable_bucket", True)),
        "caption_extension": ds.get("caption_extension") or ".txt",
    }
    if general["enable_bucket"]:
        for k in ("bucket_reso_steps", "min_bucket_reso", "max_bucket_reso"):
            if ds.get(k) not in (None, ""):
                general[k] = int(ds[k])
    for k in ("shuffle_caption", "flip_aug"):
        if ds.get(k):
            general[k] = True
    if ds.get("keep_tokens"):
        general["keep_tokens"] = int(ds["keep_tokens"])
    subsets = []
    for s in ds.get("subsets", []):
        if not (s.get("image_dir") or "").strip():
            continue
        sub = {"image_dir": s["image_dir"].strip().replace("\\", "/"),
               "num_repeats": int(s.get("num_repeats") or 1)}
        if (s.get("class_tokens") or "").strip():
            sub["class_tokens"] = s["class_tokens"].strip()
        subsets.append(sub)
    return {"general": general,
            "datasets": [{"batch_size": int(ds.get("batch_size") or 1), "subsets": subsets}]}


def build_training_config(args, schema_args):
    """Form values -> typed dict of options to write to training.toml."""
    kinds = {a["key"]: a["kind"] for a in schema_args}
    out = {}
    for k, raw in (args or {}).items():
        kind = kinds.get(k, "str")
        v = tomlio.coerce(kind, raw)
        if v is None:
            continue
        if kind == "bool" and v is False:
            continue   # store_true flags: just leave them out
        out[k] = v
    return out


class Trainer:
    def __init__(self):
        self.lock = threading.RLock()
        self.queue_file = paths.data_dir() / "queue.json"
        q = read_json(self.queue_file, {}) or {}
        self.queue = [r for r in q.get("queue", []) if (load_run(r) or {}).get("status") == "queued"]
        self.queue_running = False      # never auto-start training when the app opens
        self.proc = None
        self.current = None             # run dict while training
        self.parser = None
        self.lines = []                 # log lines of the current run (progress lines excluded)
        self.progress_line = ""
        self.points = []
        self.stop_requested = False
        self.events = []                # small notifications for the UI (finished, failed)
        self._recover_crashed()
        threading.Thread(target=self._loop, daemon=True).start()

    # ---- queue management ------------------------------------------------

    def _persist(self):
        write_json(self.queue_file, {"queue": self.queue})

    def _recover_crashed(self):
        """Runs that were 'running' when the app closed are marked as interrupted."""
        for d in paths.runs_dir().iterdir() if paths.runs_dir().exists() else []:
            r = read_json(d / "run.json")
            if r and r.get("status") == "running":
                r["status"] = "interrupted"
                save_run(r)

    def enqueue(self, job, start=False):
        """job: {name, script, family, args, dataset, extra_args, schema_args, resume_from?}"""
        run_id = new_id()
        d = run_dir(run_id)
        d.mkdir(parents=True)
        if job.get("config") is not None:   # re-run / resume: reuse the already-typed config
            cfg = {k: v for k, v in job["config"].items() if k != "resume"}
        else:
            cfg = build_training_config(job.get("args"), job.get("schema_args", []))
        if job.get("resume_from"):
            cfg["resume"] = job["resume_from"]
        ds = build_dataset_toml(job.get("dataset", {}))
        sample_prompts = None
        scfg = job.get("samples") or {}
        accepts = {a["key"] for a in job.get("schema_args") or []}
        # The "Make previews while training" switch decides about samples. Drop any sample settings
        # that came in some other way (e.g. an imported .toml or "All options"), so that "off" means off
        # and "on" uses exactly what the Sample images card says.
        for k in SAMPLE_KEYS:
            if k != "sample_sampler" or not scfg.get("enabled"):
                cfg.pop(k, None)
        if scfg.get("enabled") and (not accepts or "sample_prompts" in accepts):
            trig = job.get("trigger") or (job.get("lora_info") or {}).get("trigger") or ""
            lines = samples.prompt_lines(scfg, trig, flow_shift=not accepts or "discrete_flow_shift" in accepts)
            if lines:
                (d / "sample_prompts.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
                cfg["sample_prompts"] = str(d / "sample_prompts.txt").replace("\\", "/")
                cfg["sample_every_n_epochs"] = max(1, int(scfg.get("every_n_epochs") or 1))
                if scfg.get("at_first"):
                    cfg["sample_at_first"] = True
                sample_prompts = [pos for pos, _ in samples.prompt_list(scfg, trig)]
        (d / "training.toml").write_text(tomlio.dumps(cfg), encoding="utf-8")
        (d / "dataset.toml").write_text(tomlio.dumps(ds), encoding="utf-8")
        st = sdscripts.status()
        run = {
            "id": run_id,
            "name": job.get("name") or cfg.get("output_name") or "Untitled run",
            "script": job["script"],
            "family": job.get("family", ""),
            "args": job.get("args", {}),
            "dataset": job.get("dataset", {}),
            "extra_args": job.get("extra_args", ""),
            "config": cfg,
            "sd_commit": st.get("commit", ""),
            "sd_branch": st.get("branch", ""),
            "status": "queued",
            "created": time.time(),
            "started": None, "finished": None, "exit_code": None,
            "progress": None, "checkpoints": [],
            "resume_from": job.get("resume_from"),
            "parent": job.get("parent"),
            "samples": scfg or None,
            "sample_prompts": sample_prompts or job.get("sample_prompts"),
            "lora_info": job.get("lora_info"),
            "trigger": job.get("trigger"),
            "send_to_swarm": job.get("send_to_swarm"),
            "send_to_comfy": job.get("send_to_comfy"),
        }
        from . import estimate
        est = estimate.safe_estimate({**job, "args": job.get("args") or {}, "dataset": job.get("dataset") or {}})
        run["estimate"] = est.get("seconds") if est else None
        save_run(run)
        with self.lock:
            self.queue.append(run_id)
            if start:
                self.queue_running = True
            self._persist()
        return run_id

    def remove(self, run_id):
        with self.lock:
            if run_id in self.queue:
                self.queue.remove(run_id)
                self._persist()
                r = load_run(run_id)
                if r:
                    r["status"] = "cancelled"
                    save_run(r)

    def move(self, run_id, delta):
        with self.lock:
            if run_id not in self.queue:
                return
            i = self.queue.index(run_id)
            j = max(0, min(len(self.queue) - 1, i + delta))
            self.queue.insert(j, self.queue.pop(i))
            self._persist()

    def set_running(self, flag):
        with self.lock:
            self.queue_running = bool(flag)

    def stop_current(self):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                self.stop_requested = True
                kill_tree(self.proc)
                return True
        return False

    # ---- runner ------------------------------------------------------------

    def _loop(self):
        while True:
            time.sleep(0.5)
            with self.lock:
                if self.current or not self.queue_running or not self.queue:
                    continue
                run_id = self.queue.pop(0)
                self._persist()
            run = load_run(run_id)
            if not run or run.get("status") != "queued":
                continue
            try:
                self._execute(run)
            except Exception as e:  # never let the runner thread die
                self._log(f">> Launcher error: {e}")
                run["status"] = "failed"
                run["error"] = str(e)
                self._finish(run)
            # Last one in the queue and not stopped by hand: "When the queue is done" (sleep/shut down)
            with self.lock:
                last = not self.queue
            if last and run.get("status") in ("done", "failed"):
                from . import power
                power.queue_finished()

    def _own_folder(self, run, d):
        """Give this run its own output folder, chosen as it starts (so two queued runs with the same
        name can't take the same one): <output_dir>/<output_name>, or "<name> (2)", "(3)"… if that
        folder already has files. Nothing from an earlier run is ever overwritten."""
        cfg = run.get("config") or {}
        if not settings.get("run_folders") or run.get("own_folder"):
            return
        out, name = cfg.get("output_dir"), str(cfg.get("output_name") or "").strip()
        if not out or not name:
            return
        base = Path(str(out)).expanduser()
        folder_name = safe_folder_name(name)
        # A re-run/resume copies the old run's config, whose output_dir is already a run folder:
        # put the new folder next to it instead of inside it.
        if re.fullmatch(re.escape(folder_name) + r"( \(\d+\))?", base.name):
            base = base.parent
        target = base / folder_name
        n = 2
        while target.exists() and any(target.iterdir()):
            target = base / f"{folder_name} ({n})"
            n += 1
        target.mkdir(parents=True, exist_ok=True)
        cfg["output_dir"] = str(target).replace("\\", "/")
        run["config"] = cfg
        run["own_folder"] = cfg["output_dir"]
        (d / "training.toml").write_text(tomlio.dumps(cfg), encoding="utf-8")
        save_run(run)

    def _command(self, run):
        repo = sdscripts.root()
        if not repo or not sdscripts.is_sd_scripts(repo):
            raise RuntimeError("sd-scripts folder isn't set up. Open the sd-scripts page first.")
        d = run_dir(run["id"])
        script = Path(repo) / run["script"]
        if not script.exists():
            raise RuntimeError(f"{run['script']} doesn't exist in this sd-scripts version.")
        tail = [str(script), f"--config_file={d / 'training.toml'}", f"--dataset_config={d / 'dataset.toml'}"]
        tail += split_cli_args(run.get("extra_args", ""))
        launcher = settings.get("launcher")
        py = sdscripts.venv_python(repo)
        if launcher == "python":
            return [py or "python", *tail]
        acc = sdscripts.accelerate_exe(repo)
        acc_args = split_cli_args(settings.get("accelerate_args"))
        if acc:
            return [acc, "launch", *acc_args, *tail]
        return [py or "python", "-m", "accelerate.commands.launch", *acc_args, *tail]

    def _log(self, line):
        self.lines.append(line)
        if len(self.lines) > 20000:
            del self.lines[:5000]

    def _execute(self, run):
        d = run_dir(run["id"])
        self._own_folder(run, d)
        with self.lock:
            self.current = run
            self.parser = LogParser()
            self.lines, self.points, self.progress_line = [], [], ""
            self.stop_requested = False
        cmd = self._command(run)
        run.update(status="running", started=time.time(), command=cmd)
        save_run(run)
        self._log(f">> {run['name']}  ·  {run['script']}")
        self._log(">> " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
        logf = open(d / "log.txt", "w", encoding="utf-8")
        logf.write("\n".join(self.lines) + "\n")
        mf = open(d / "metrics.csv", "w", newline="", encoding="utf-8")
        mw = csv.writer(mf)
        mw.writerow(["step", "epoch", "loss", "t"])
        last_logged_pct = -1
        last_save = time.time()
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=str(sdscripts.root()), env=child_env(), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                **popen_kwargs())
            for raw in self.proc.stdout:   # universal newlines: tqdm's \r splits lines too
                line = raw.rstrip("\n")
                if not line.strip():
                    continue
                is_prog, point = self.parser.feed(line)
                if is_prog:
                    self.progress_line = line.strip()
                    pct = self.parser.progress["percent"]
                    if pct != last_logged_pct:
                        logf.write(line.strip() + "\n")
                        last_logged_pct = pct
                else:
                    self._log(line)
                    logf.write(line + "\n")
                if point:
                    self.points.append(point)
                    mw.writerow([point["step"], point["epoch"], point["loss"], point["t"]])
                if time.time() - last_save > 5:
                    run["progress"] = dict(self.parser.progress)
                    run["checkpoints"] = list(self.parser.checkpoints)
                    save_run(run)
                    logf.flush()
                    mf.flush()
                    last_save = time.time()
            self.proc.wait()
            code = self.proc.returncode
        finally:
            logf.close()
            mf.close()
        run["exit_code"] = code
        if self.stop_requested:
            run["status"] = "stopped"
        else:
            run["status"] = "done" if code == 0 else "failed"
        self._log(f"\n>> Finished with exit code {code} ({run['status']}).")
        with open(d / "log.txt", "a", encoding="utf-8") as f:
            f.write(self.lines[-1] + "\n")
        run["progress"] = dict(self.parser.progress)
        run["checkpoints"] = list(self.parser.checkpoints)
        self._finish(run)

    def _after_success(self, run):
        """Write LoRA info into the saved files, then optionally copy them into SwarmUI."""
        from . import metadata, runs, swarm
        info = run.get("lora_info") or {}
        if any(info.get(k) for k in ("title", "description", "author", "trigger", "tags")) or info.get("thumbnail"):
            thumb = None
            if info.get("thumbnail") == "sample":
                grid = samples.find(run)
                cells = [c for c in grid["cells"] if c["row"] == 0] or grid["cells"]
                if cells:
                    thumb = max(cells, key=lambda c: c["mtime"])["path"]
            ups = metadata.info_updates(info, thumb)
            for o in runs.outputs(run):
                try:
                    metadata.write(o["path"], ups)
                except Exception as e:
                    self._log(f">> Couldn't write LoRA info to {o['name']}: {e}")
            self._log(">> LoRA info written to the saved files.")
        if run.get("send_to_comfy"):
            from . import comfy
            try:
                which = run["send_to_comfy"] if run["send_to_comfy"] in ("all", "final") else "final"
                res = comfy.send_run(run["id"], which)
                self._log(f">> Copied {len(res['copied'])} file(s) to ComfyUI: {res['folder']}")
                run.update(trainer_reload(run["id"]) or {})
            except Exception as e:
                self._log(f">> Couldn't copy to ComfyUI: {e}")
        if run.get("send_to_swarm"):
            try:
                res = swarm.send_run(run["id"], run.get("send_to_swarm") if run.get("send_to_swarm") in ("all", "final") else "final")
                self._log(f">> Copied {len(res['copied'])} file(s) to SwarmUI: {res['folder']}")
                run.update(trainer_reload(run["id"]) or {})
            except Exception as e:
                self._log(f">> Couldn't copy to SwarmUI: {e}")

    def _notify(self, run):
        from . import notify
        from .util import fmt_duration
        dur = fmt_duration((run.get("finished") or 0) - (run.get("started") or 0)) if run.get("started") else ""
        loss = (run.get("progress") or {}).get("loss")
        if run["status"] == "done":
            nxt = f" · {len(self.queue)} more queued" if self.queue and self.queue_running else ""
            notify.toast("Training finished", f"{run['name']} · {dur}{f' · loss {loss:.4f}' if loss else ''}{nxt}")
        elif run["status"] == "failed":
            notify.toast("Training failed", f"{run['name']}: open LoRA Studio to see the log.")

    def _finish(self, run):
        if run.get("status") == "done":
            before = len(self.lines)
            try:
                self._after_success(run)
            except Exception as e:
                self._log(f">> Post-training step failed: {e}")
            if len(self.lines) > before:
                with open(run_dir(run["id"]) / "log.txt", "a", encoding="utf-8") as f:
                    f.write("\n".join(self.lines[before:]) + "\n")
        run["finished"] = time.time()
        save_run(run)
        with self.lock:
            self.events.append({"t": time.time(), "type": run["status"], "run": run["id"],
                                "name": run["name"]})
            self.events = self.events[-50:]
            self.current = None
            self.proc = None
            if run["status"] == "stopped":
                self.queue_running = False   # a manual stop pauses the queue
        try:
            self._notify(run)
        except Exception:
            pass

    # ---- UI polling ----------------------------------------------------------

    def state(self):
        with self.lock:
            cur = None
            if self.current:
                cur = {k: self.current.get(k) for k in ("id", "name", "script", "family", "started")}
                cur["progress"] = dict(self.parser.progress) if self.parser else None
                cur["log_total"] = len(self.lines)
                cur["points_total"] = len(self.points)
            queued = []
            for rid in self.queue:
                r = load_run(rid)
                if r:
                    queued.append({k: r.get(k) for k in ("id", "name", "script", "family", "created", "estimate")})
            from . import power
            return {"running": self.queue_running, "current": cur, "queue": queued,
                    "events": self.events[-10:], "power": power.get()}

    def live_log(self, run_id, since):
        with self.lock:
            if self.current and self.current["id"] == run_id:
                return {"live": True, "lines": self.lines[since:], "total": len(self.lines),
                        "progress_line": self.progress_line}
        return None

    def live_points(self, run_id, since):
        with self.lock:
            if self.current and self.current["id"] == run_id:
                return {"live": True, "points": self.points[since:], "total": len(self.points)}
        return None


_trainer = None


def get():
    global _trainer
    if _trainer is None:
        _trainer = Trainer()
    return _trainer

