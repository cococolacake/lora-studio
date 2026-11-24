# Training

On the **Train** page, pick a script on the left, fill in the form, then **Train now** or **Add to queue**.

## The form

- **Any sd-scripts training script:** SD 1.x/2.x, SDXL, SD3, FLUX, Anima, Lumina and more. The form is built from the script's own options, so new options appear automatically when sd-scripts updates.
- **Simple and full views:** *Simple* shows the settings that matter; *All options* lists every one, with search.
- **Check before training:** wrong values, missing models or empty image folders are caught in seconds, before the model loads.
- **Time estimates:** see roughly how long a run will take before you start; LoRA Studio learns your GPU's speed from past runs.

## Presets

Save your favourite setups, or import existing `training.toml` / `dataset_config.toml` files. Pick a **default preset** that every **New session** starts from, and **share presets** as small files (your own paths are left out).

## The queue

Line up several runs and walk away. Watch live loss, speed, time left and the log. Waiting runs can be reordered or removed.

- **GPU monitor:** VRAM, load, temperature and power while you train.
- **Notifications:** a desktop notification when a run finishes or fails.
- **Overnight batches:** let the PC sleep or shut down when the queue is done (with a 1-minute countdown you can cancel).

## Runs

Every run keeps its exact config, sd-scripts version, loss curve and log. Re-run it, tweak it, or **resume** from a saved state.

### Resuming a run

Turn on **Save state** (Train → Output) before training. If a run is stopped or crashes, open it on the Runs page and press **Resume**.

## Samples and the best epoch

- **Sample previews:** your prompts are rendered every epoch and shown as a prompt × epoch grid. **Compare** any two with a slider or fade, or turn a prompt's samples into an **animated GIF**.
- **Best epoch:** star the epoch you like in the sample grid; it's saved as `…-best.safetensors` and can be copied to SwarmUI or ComfyUI in one click (see [SwarmUI and ComfyUI](SwarmUI-and-ComfyUI)).
