# Contributing

Thanks for wanting to help! Bug reports, ideas and pull requests are all welcome. How to *use* LoRA Studio is in the [wiki](https://github.com/cococolacake/lora-studio/wiki); this file is about working on it.

## Running from source

```
git clone https://github.com/cococolacake/lora-studio
cd lora-studio
python -m pip install -r requirements.txt
python main.py --browser
```

Python 3.10 or newer. `--browser` opens LoRA Studio in a normal browser tab with its dev tools; `python main.py --debug` opens the app window with developer tools (right-click → Inspect).

## Tests

```
python -m pytest -q tests
```

No GPU or sd-scripts needed.

Check for leftover code (unused imports and variables, names defined twice, unreachable code). CI runs the same. `npm install --no-save` removes whatever it installed before, so install ESLint again after the smoke test's Playwright install:

```
python -m pip install ruff
ruff check .
npm install --no-save eslint@9
npx eslint .
```

There's also a browser smoke test that opens every page and dataset tool and fails on any JavaScript error (it's what CI runs):

```
npm install --no-save playwright@1 && npx playwright install chromium
python main.py --browser --port 8765 &
SMOKE_URL=http://127.0.0.1:8765 SMOKE_DATASET=/path/to/images node tests/smoke.mjs
```

## Screenshots

The screenshots in `docs/screenshots/` (used by the README and the wiki) come from a script. It starts LoRA Studio in a temporary data folder with a made-up dataset, and a fake trainer stands in for sd-scripts, so no GPU or sd-scripts install is needed. To retake all of them after a UI change, close LoRA Studio and run:

```
python -m pip install playwright pillow
python -m playwright install chromium
python docs/screenshots/take.py
```

It takes about two minutes, most of it waiting for the fake training runs.

## How the code is laid out

The app is plain Python plus HTML/CSS/JS with **no build step**.

```
main.py                 starts the window (or --browser for a normal browser tab)
install.sh, lora-studio.sh, create-desktop-entry.sh   the Linux versions of the .bat files
tests/                  quick checks (python -m pytest tests) + a browser smoke test, run on every pull request
wiki/                   the wiki pages (published to the Wiki tab when merged)
studio/                 Python backend
  api.py                every function the UI can call
  sdscripts.py          find / install / update / switch / roll back sd-scripts; read a script's options
  _schema_dump.py       runs inside the sd-scripts venv to read argparse options
  trainer.py            queue, launching, live log + loss parsing
  runs.py               run history, resume points, outputs
  dataset_tools.py      captions, bulk edits, rename, crop/resize, delete/restore, autocomplete
  health.py             dataset health check + bucket/step estimate
  samples.py            sample prompt files and sample-image discovery
  metadata.py           read/write .safetensors metadata (no torch needed)
  swarm.py              SwarmUI: detect, launch, copy LoRAs, test grids
  gallerydl.py          gallery-dl: install, site logins, downloads
  importer.py           downloaded folder → clean numbered, captioned dataset
  estimate.py           training-time estimates from past runs
  gpu.py / notify.py    nvidia-smi stats / desktop notifications
  backup.py             backup & restore of LoRA Studio's own data
  comfy.py              ComfyUI: inside SwarmUI or a separate install
  csstheme.py           CSS themes dropped into Settings > Appearance
  workers/              tagger + duplicate finder; these run inside the sd-scripts venv
web/                    the UI
  css/tokens.css        theme colours (the glass themes, light and dark)
  css/glass.css         the glass look (panels, rail, buttons)
  css/app.css           components
  css/custom.css        user overrides (never touched by updates)
  js/pages/*.js         one file per page
  js/tools/*.js         dataset tools
```

## A few house rules

- **Keep it working on Python 3.10**, on Windows and Linux.
- **No build step** for the front end, and as few new dependencies as possible. LoRA Studio's own dependencies stay small; anything heavy runs inside the user's sd-scripts venv.
- **Write the UI in plain words.** Buttons say what they do; messages say what happened and what to do next.

## Pull requests and releases

Small and focused is easiest to review. Add a test when you fix a bug or add a feature, and fill in the template:

- **What changed**: for reviewers.
- **Release notes**: for users. Keep this section last.

Merging is always **Squash and merge**, so each pull request becomes one commit on `main`.

**Releasing:** bump `__version__` in `studio/__init__.py` in the pull request. When it's merged, the Release workflow posts the release with the pull request's **Release notes**. A pull request that doesn't bump the version isn't released on its own: its notes are added to the next release (write `None` for changes users don't need to hear about). The workflow can also be run by hand from the Actions tab. The in-app updater offers the newest release.

**The wiki** is written in `wiki/`. When a change to it is merged, the Wiki workflow publishes it to the Wiki tab, so edit the files here rather than on the website.
