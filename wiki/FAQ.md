# FAQ

**Does LoRA Studio download PyTorch?**
No. All the heavy machine-learning parts run inside your sd-scripts install, so nothing big is downloaded twice. LoRA Studio itself only needs `pywebview` and `Pillow`.

**I don't have sd-scripts yet.**
On first launch, LoRA Studio can install a fresh copy for you. See [Getting started](Getting-started).

**Where are my settings stored?**
In LoRA Studio's data folder: `%APPDATA%\LoRA Studio` on Windows, `~/.local/share/lora-studio` on Linux. **Settings → Folders & backup** has an **Open folder** button.

**A run stopped or crashed. Can I continue it?**
Yes, if **Save state** (Train → Output) was on before training. Open the run on the Runs page and press **Resume**. See [Training](Training#resuming-a-run).

**What are the `_originals`, `_deleted` and `_duplicates` folders in my dataset?**
They keep originals of cropped or resized images, images you deleted in the viewer (with their captions), and images moved by the duplicate finder. sd-scripts ignores them. See [Datasets](Datasets#folders-lora-studio-creates-in-your-dataset).

**Will an update overwrite my changes?**
No. Updating keeps your `.venv`, your `custom.css`, CSS themes and all your settings, runs and presets. See [Updating and backups](Updating-and-backups).

**What does a backup include?**
Your settings, presets, themes and run history. Datasets, trained LoRAs and site logins aren't included.

**Is LoRA Studio part of sd-scripts, SwarmUI or ComfyUI?**
No. It's an independent project and isn't affiliated with kohya-ss, SwarmUI, ComfyUI or Stability AI.

**I found a bug or have an idea.**
[Open an issue](https://github.com/cococolacake/lora-studio/issues/new/choose).
