# Getting started

## What you need

- **Windows 10 or 11**, or **Linux** (see [Linux](#linux)). On Windows the app window uses Microsoft Edge WebView2, which is built in.
- **Python 3.10 or newer**, from [python.org](https://www.python.org/downloads/). Tick **"Add python.exe to PATH"** when installing.
- **Git**, from [git-scm.com](https://git-scm.com/download/win).
- **sd-scripts.** If you don't have it yet, LoRA Studio can install it for you.

LoRA Studio itself is small. All the heavy machine-learning parts (PyTorch etc.) run inside **your sd-scripts install**, so nothing big is downloaded twice.

## Install on Windows

1. **Download** the latest version from [Releases](https://github.com/cococolacake/lora-studio/releases/latest) (or the green **Code** button → **Download ZIP**). Unzip it somewhere permanent, e.g. `C:\AI\lora_studio`.
2. **Double-click `Install.bat`.** It creates a private Python environment in the folder and installs two small packages (`pywebview` and `Pillow`).
3. **Double-click `LoRA Studio.bat`** to start. Optionally run `Create desktop shortcut.bat` once for a desktop and Start menu shortcut.
4. On first launch, **point it at your sd-scripts folder** (the one with `train_network.py`), or let it install a fresh copy.

## Linux

1. Download and unzip LoRA Studio (or clone it), then open a terminal in its folder.
2. Run `./install.sh`. It makes a private Python environment and installs LoRA Studio's small dependencies. The app window needs GTK or Qt: it uses GTK + WebKit if your desktop already has them, and otherwise installs Qt with pip. Use `./install.sh --gtk` or `--qt` to choose, or `--browser` to skip both and use your web browser.
3. Run `./lora-studio.sh` to start (`--browser` opens it in your web browser).
4. Optional: `./create-desktop-entry.sh` adds LoRA Studio to your app menu (`--remove` takes it out again).

Your settings live in `~/.local/share/lora-studio`.

## A tour of the pages

| Page | What it's for |
|---|---|
| **Home** | What's training, what's queued, recent results, sd-scripts status |
| **Train** | Pick a script on the left, fill in the form, then **Train now** or **Add to queue**. See [Training](Training). |
| **Queue** | Live progress, loss chart and log; reorder or remove waiting runs |
| **Runs** | Past runs: loss curve, samples, saved LoRAs and their info, resume, config and log |
| **Dataset** | New dataset (gallery-dl), images & tags, health check, duplicates, crop & resize, rename. See [Datasets](Datasets). |
| **SwarmUI & ComfyUI** | Start/open either one, use it inside the app, and see the LoRAs you've sent it. See [SwarmUI and ComfyUI](SwarmUI-and-ComfyUI). |
| **sd-scripts** | Update, switch branch, roll back |
| **Settings** | Appearance, launcher options, notifications, folders, backup & restore |
