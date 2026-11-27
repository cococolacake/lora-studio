# Retakes the README and wiki screenshots, with a fake trainer standing in for sd-scripts (no GPU needed).
#   python -m pip install playwright pillow && python -m playwright install chromium
#   python docs/screenshots/take.py
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SIZE = {"width": 1440, "height": 900}
PORT = 8765
# The server, without the browser tab it would open in --browser mode.
SERVER = "import runpy, sys, webbrowser; webbrowser.open = lambda *a, **k: None; sys.argv = ['main.py'] + sys.argv[1:]; runpy.run_path('main.py', run_name='__main__')"
SCRIPTS = ["anima_train_network.py", "flux_train_network.py", "sdxl_train_network.py", "sdxl_train.py",
           "train_network.py", "train_textual_inversion.py"]
CAPTIONS = ["1girl, solo, smile, looking at viewer, upper body", "1girl, full body, standing, outdoors",
            "1girl, sitting, reading a book, window light", "1girl, portrait, close-up, soft lighting"]
PROMPTS = "1girl, solo, smile, looking at viewer, upper body\n1girl, full body, standing, outdoors\n1girl, sitting, reading a book, window light"
HIDE_PATHS_JS = r"""(pairs) => {
  const swap = (s) => pairs.reduce((t, [from, to]) => t.split(from).join(to), s);
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  // a Windows path keeps its backslashes after the swap: /home/you\datasets becomes /home/you/datasets
  const tidy = (s) => swap(s).replace(/\/home\/you[^\s"'<>]*/g, (p) => p.split("\\").join("/"));
  for (let n; (n = walk.nextNode());) n.nodeValue = tidy(n.nodeValue);
  for (const el of document.querySelectorAll("input, textarea")) { el.value = tidy(el.value); el.placeholder = tidy(el.placeholder); }
}"""


def make_sd_scripts(d):
    """A folder LoRA Studio accepts as sd-scripts, where every training script is the fake trainer."""
    (d / "library").mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(d / "venv")], check=True)
    for name in SCRIPTS:
        shutil.copy(HERE / "fake_trainer.py", d / name)
    # a git checkout, so the sd-scripts card shows a branch and commit
    git = ["git", "-C", str(d), "-c", "user.name=LoRA Studio", "-c", "user.email=screenshots@example.com"]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "Update README"], check=True)


def make_dataset(d):
    d.mkdir(parents=True)
    for i in range(12):
        im = Image.new("RGB", (768 + 128 * (i % 3), 1024), (200 - 6 * i, 190, 245 - 4 * i))
        draw = ImageDraw.Draw(im)
        draw.ellipse((260, 220, 540, 500), fill=(255, 214, 190))
        draw.rectangle((230, 560, 570, 1024), fill=(150 - 5 * i, 120, 230))
        im.save(d / f"image_{i + 1:02}.png")
        (d / f"image_{i + 1:02}.txt").write_text(CAPTIONS[i % len(CAPTIONS)], encoding="utf-8")


def main():
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            sys.exit(f"Something is already using port {PORT}. Close LoRA Studio and run this again.")
    base = f"http://127.0.0.1:{PORT}"

    def api(method, *args):
        req = urllib.request.Request(f"{base}/api/{method}", json.dumps({"args": list(args)}).encode(),
                                     {"Content-Type": "application/json"})
        reply = json.load(urllib.request.urlopen(req))
        if reply.get("error"):
            raise RuntimeError(f"{method}: {reply['error']}")
        return reply.get("result")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp).resolve()   # the long form, in case Windows handed out a short C:\Users\COCO~1 path
        make_sd_scripts(tmp / "sd-scripts")
        make_dataset(tmp / "datasets" / "my_character")
        # Shown in place of the temporary folder, so no temp path or username appears.
        swaps = [[str(tmp).replace("\\", "/"), "/home/you"], [str(tmp), "/home/you"]]
        server = subprocess.Popen([sys.executable, "-c", SERVER, "--browser", "--port", str(PORT)], cwd=ROOT,
                                  env={**os.environ, "LORA_STUDIO_HOME": str(tmp / "data")},
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                if server.poll() is not None:
                    sys.exit("LoRA Studio didn't start. Run `python main.py --browser` to see why.")
                try:
                    api("bootstrap")
                    break
                except OSError:
                    time.sleep(0.5)
            theme = api("bootstrap")["settings"]["theme"]
            # the solid look while training would hide the glass in every shot
            api("save_settings", {"sd_scripts_dir": str(tmp / "sd-scripts"), "launcher": "python",
                                  "theme": {**theme, "simpleWhileTraining": False}})
            take(api, base, tmp, swaps)
        finally:
            # the server doesn't stop a training when it's closed this way, so stop it first
            try:
                api("stop_current")
            except OSError:
                pass
            server.terminate()
            server.wait(10)


def job_for(api, tmp, name, delay):
    script = "anima_train_network.py"
    schema = api("schema", script)
    return {
        "name": name, "script": script, "family": "Anima",
        "args": {"pretrained_model_name_or_path": str(tmp / "models" / "anima.safetensors"),
                 "output_dir": str(tmp / "output" / name.replace(" ", "_")), "output_name": name.replace(" ", "_"),
                 "max_train_epochs": "6", "save_state": True},
        "dataset": {"subsets": [{"image_dir": str(tmp / "datasets" / "my_character"), "num_repeats": 2}]},
        "extra_args": f"--fake_steps 140 --fake_delay {delay}",
        "schema_args": [{"key": a["key"], "kind": a["kind"]} for a in schema["args"]],
        "samples": {**schema["sample_defaults"], "enabled": True, "prompts": PROMPTS},
    }


def wait_for(api, run_id, ready):
    while True:
        status = next(r["status"] for r in api("runs") if r["id"] == run_id)
        if ready(status):
            if status not in ("running", "done"):
                sys.exit(f"A fake training run ended as {status!r}. Its log is on the Runs page.")
            return
        if status not in ("queued", "running"):
            sys.exit(f"A fake training run ended as {status!r} too early.")
        time.sleep(0.5)


def take(api, base, tmp, swaps):
    # Two finished runs for the history and the sample grid, then one that's still training during the shots.
    for name in ("my_character v0", "my_character v1"):
        finished = api("enqueue", job_for(api, tmp, name, 0.01), True)
        wait_for(api, finished, lambda status: status not in ("queued", "running"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=SIZE)

        def shot(name, js=None, wait=1200):
            if js:
                page.evaluate(js)
            page.wait_for_timeout(wait)
            page.evaluate(HIDE_PATHS_JS, swaps)
            save(page, name)

        page.goto(base)
        page.wait_for_function("window.ctx && window.ctx.boot")
        # Before the live run starts, so the dataset pages don't say it's training on this folder.
        page.evaluate('ctx.go("dataset", { tool: "viewer" })')
        page.wait_for_timeout(800)
        folder = page.locator("#main input.input.mono").first
        folder.fill(str(tmp / "datasets" / "my_character"))
        folder.dispatch_event("change")
        page.click('#main button:has-text("Load")')
        page.wait_for_selector(".vtile")
        page.locator(".vtile").nth(2).click()
        shot("images-and-tags")
        page.click('#main button:has-text("Crop")')
        shot("crop")
        page.keyboard.press("Escape")
        page.evaluate(f'ctx.go("runs", {{ run: "{finished}" }})')
        page.wait_for_timeout(1200)
        page.evaluate("""() => {
          const c = [...document.querySelectorAll(".card")].find((el) => el.querySelector(".card-title")?.textContent === "Samples");
          c.style.scrollMarginTop = "160px";   // some of the Loss card above, so it reads as a scrolled page
          c.scrollIntoView({ block: "start" });
        }""")
        shot("samples")
        # back to the default for this one shot, since this page shows the setting itself
        theme = api("bootstrap")["settings"]["theme"]
        api("save_settings", {"theme": {**theme, "simpleWhileTraining": True}})
        page.reload()
        page.wait_for_function("window.ctx && window.ctx.boot")
        shot("appearance", 'ctx.go("settings", { section: "appearance" })')
        api("save_settings", {"theme": {**theme, "simpleWhileTraining": False}})
        page.reload()
        page.wait_for_function("window.ctx && window.ctx.boot")

        live = api("enqueue", job_for(api, tmp, "my_character v2", 0.05), True)
        # partway into epoch 3, so the loss chart has a shape
        wait_for(api, live, lambda status: status == "running" and api("run_metrics", live)["total"] >= 350)
        shot("home", 'ctx.go("home")')
        shot("queue", 'ctx.go("queue")')
        page.click('.rail-btn:has-text("Dark")')
        shot("home-dark", 'ctx.go("home")')
        page.click('.rail-btn:has-text("Light")')
        page.wait_for_timeout(600)
        shot("train", 'ctx.go("train")')
        browser.close()


def save(page, name):
    Image.open(BytesIO(page.screenshot())).save(HERE / f"{name}.webp", "WEBP", quality=82, method=6)
    print(name)


if __name__ == "__main__":
    main()
