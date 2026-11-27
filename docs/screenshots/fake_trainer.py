"""A stand-in for an sd-scripts training script, used only by take.py: it trains nothing.

It prints progress the way sd-scripts does and writes sample images and small LoRA files, so LoRA Studio
shows real training screens without a GPU. --fake_steps sets the steps per epoch, --fake_delay the seconds per step.
Standard library only, so it runs in a bare venv like the real scripts' would.
"""
import argparse
import random
import re
import struct
import sys
import time
import zlib
from pathlib import Path


def setup_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--config_file")
    p.add_argument("--dataset_config")
    p.add_argument("--pretrained_model_name_or_path", help="Base model file")
    p.add_argument("--output_dir", help="Where the trained LoRA goes")
    p.add_argument("--output_name", help="File name for the trained LoRA")
    p.add_argument("--max_train_epochs", type=int, default=6)
    p.add_argument("--save_every_n_epochs", type=int, default=1)
    p.add_argument("--save_state", action="store_true")
    p.add_argument("--learning_rate", type=float, default=1e-4)
    p.add_argument("--unet_lr", type=float)
    p.add_argument("--optimizer_type", default="AdamW8bit", choices=["AdamW", "AdamW8bit", "Prodigy", "Lion"])
    p.add_argument("--lr_scheduler", default="cosine", choices=["constant", "cosine", "linear"])
    p.add_argument("--network_module", default="networks.lora")
    p.add_argument("--network_dim", type=int, default=16)
    p.add_argument("--network_alpha", type=float, default=8)
    p.add_argument("--train_batch_size", type=int, default=2)
    p.add_argument("--resolution", default="1024,1024")
    p.add_argument("--mixed_precision", default="bf16", choices=["no", "fp16", "bf16"])
    p.add_argument("--gradient_checkpointing", action="store_true")
    p.add_argument("--cache_latents", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--sample_prompts")
    p.add_argument("--sample_every_n_epochs", type=int)
    p.add_argument("--sample_at_first", action="store_true")
    p.add_argument("--sample_sampler", default="euler_a")
    p.add_argument("--fake_steps", type=int, default=140)
    p.add_argument("--fake_delay", type=float, default=0.002)
    return p


def toml_value(text, key):
    """One plain value from LoRA Studio's training.toml (no TOML library needed)."""
    m = re.search(rf'^{key}\s*=\s*(.+)$', text, re.M)
    return m.group(1).strip().strip('"').replace("\\\\", "\\") if m else None


def clock(s):
    return f"{int(s) // 60:02d}:{int(s) % 60:02d}"


def sample(path, epoch, row, size=256):
    """A simple figure that grows each epoch, written as a PNG by hand."""
    bg = tuple(max(0, c - 8 * epoch) for c in [(205, 215, 250), (220, 200, 245), (235, 185, 240)][row % 3])
    body = (140 - 10 * row, 120, 230 - 20 * row)
    r = 35 + 6 * epoch
    rows = []
    for y in range(size):
        line = bytearray(b"\0")
        for x in range(size):
            if (x - 128) ** 2 + (y - 100) ** 2 < r * r:
                line += bytes((255, 214, 190))
            elif 93 <= x < 163 and y >= 150:
                line += bytes(body)
            else:
                line += bytes(bg)
        rows.append(bytes(line))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def main():
    args = setup_parser().parse_args()
    cfg = Path(args.config_file).read_text(encoding="utf-8")
    out = Path(toml_value(cfg, "output_dir"))
    name = toml_value(cfg, "output_name") or "lora"
    epochs = int(toml_value(cfg, "max_train_epochs") or args.max_train_epochs)
    prompts_file = toml_value(cfg, "sample_prompts")
    prompts = [ln for ln in Path(prompts_file).read_text(encoding="utf-8").splitlines() if ln.strip()] if prompts_file else []
    out.mkdir(parents=True, exist_ok=True)
    total = epochs * args.fake_steps
    rng = random.Random(args.seed)
    print(f"loading dataset from {args.dataset_config}", flush=True)
    start = time.time()
    step = 0
    for epoch in range(1, epochs + 1):
        print(f"epoch {epoch}/{epochs}", flush=True)
        for _ in range(args.fake_steps):
            step += 1
            time.sleep(args.fake_delay)
            loss = 0.17 * (1 - 0.5 * step / total) + rng.uniform(-0.012, 0.012)
            spent = time.time() - start
            speed = step / spent if spent else 0
            left = (total - step) / speed if speed else 0
            pct = 100 * step // total
            bar = "█" * (pct // 10)
            sys.stdout.write(f"steps: {pct:3d}%|{bar:<10}| {step}/{total} [{clock(spent)}<{clock(left)}, {speed:.2f}it/s, avr_loss={loss:.4f}]\r")
            sys.stdout.flush()
        if epoch % args.save_every_n_epochs == 0:
            f = out / f"{name}-{epoch:06d}.safetensors" if epoch < epochs else out / f"{name}.safetensors"
            f.write_bytes(bytes(568))
            print(f"\nsaving checkpoint: {f}", flush=True)
            if "save_state = true" in cfg:
                (out / f"{name}-{epoch:06d}-state").mkdir(exist_ok=True)
        if prompts:
            (out / "sample").mkdir(exist_ok=True)
            stamp = time.strftime("%Y%m%d%H%M%S")
            for row in range(len(prompts)):
                sample(out / "sample" / f"{name}_e{epoch:06d}_{row:02d}_{stamp}_42.png", epoch, row)
    print("\nmodel saved.", flush=True)


if __name__ == "__main__":
    main()
