# SwarmUI and ComfyUI

Both live on the **Generate** page in the rail.

- **Start them from the app:** use your existing SwarmUI and/or ComfyUI install, and open either one right inside LoRA Studio.
- **ComfyUI two ways:** the ComfyUI that runs inside SwarmUI (no extra setup), or a separate ComfyUI install (portable or git).
- **Copy LoRAs over:** finished LoRAs go straight into SwarmUI or ComfyUI. Title, trigger word and thumbnail are stored in the file, where SwarmUI's model browser shows them.
- **Test grids:** render epoch × strength grids through SwarmUI.

## SwarmUI

Choose your SwarmUI folder on the SwarmUI tab. LoRAs are copied to `<SwarmUI LoRA folder>/LoRA Studio/<name>/`. Test grids need SwarmUI running; the **Start SwarmUI** button launches it.

## ComfyUI

On the ComfyUI tab, pick **The one inside SwarmUI** (nothing else to set up) or **A separate ComfyUI install**. For a separate install, choose its folder: the portable folder with `run_nvidia_gpu.bat`, or a git install with `main.py`. LoRAs are copied to `models/loras/LoRA Studio/<name>/`; refresh ComfyUI's LoRA list to see them.
