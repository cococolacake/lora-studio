"""WD EVA02 Canary auto-tagger.

job: {images: [...], gen_threshold, char_threshold, trigger, mode: overwrite|merge|skip,
      caption_extension, blacklist: [...], batch_size}
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, load_job, need, parse_tags, progress, tag_key  # noqa: E402

REPO = "ashen-sensored/wd-eva02-tagger-2026-canary"


def main():
    job = load_job()
    np, torch, timm, hub, PIL = need("numpy", "torch", "timm", "huggingface_hub", "PIL")
    from PIL import Image

    ext = job.get("caption_extension") or ".txt"
    mode = job.get("mode", "overwrite")
    images = job["images"]
    if mode == "skip":
        images = [p for p in images if not os.path.exists(os.path.splitext(p)[0] + ext)]
    total = len(images)
    if not total:
        emit("R", {"tagged": 0, "skipped": len(job["images"])})
        return

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    progress(0, total, f"Loading the EVA02 tagger on {dev} (first time downloads ~1 GB)...")
    model = timm.create_model(f"hf-hub:{REPO}", pretrained=True, num_classes=16473).to(dev).eval()
    csv_path = hub.hf_hub_download(repo_id=REPO, filename="selected_tags.csv")
    names, cats = [], []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if row:
                names.append(row[1].strip() if len(row) > 1 else row[0].strip())
                cats.append(int(row[2].strip()) if len(row) > 2 and row[2].strip().isdigit() else 0)

    gen_t = float(job.get("gen_threshold", 0.35))
    char_t = float(job.get("char_threshold", 0.75))
    trigger = (job.get("trigger") or "").strip()
    trig_k = tag_key(trigger) if trigger else None
    black = {tag_key(t) for t in job.get("blacklist") or []}
    bs = max(1, int(job.get("batch_size") or 4))
    done = 0
    for i in range(0, total, bs):
        chunk = images[i:i + bs]
        tensors, ok = [], []
        for p in chunk:
            try:
                with Image.open(p) as img:
                    arr = np.array(img.convert("RGB").resize((448, 448), Image.Resampling.BICUBIC)).astype(np.float32) / 255.0
                arr = arr[:, :, ::-1].copy()
                tensors.append(torch.from_numpy(arr).permute(2, 0, 1))
                ok.append(p)
            except Exception as e:
                sys.stdout.write(f"Skipping {os.path.basename(p)}: {e}\n")
        if not tensors:
            continue
        with torch.no_grad():
            probs = torch.sigmoid(model(torch.stack(tensors).to(dev))).cpu().numpy()
        for p, row in zip(ok, probs):
            tags = []
            for idx in np.argsort(-row):
                prob = row[idx]
                if prob < min(gen_t, char_t):
                    break
                if idx >= len(names):
                    continue
                cat = cats[idx]
                if cat == 9:  # rating tags
                    continue
                if prob >= (char_t if cat == 4 else gen_t):
                    t = names[idx].replace("_", " ")
                    if tag_key(t) not in black:
                        tags.append(t)
            cap = os.path.splitext(p)[0] + ext
            if mode == "merge" and os.path.exists(cap):
                with open(cap, "r", encoding="utf-8", errors="replace") as f:
                    old = parse_tags(f.read())
                keys = {tag_key(t) for t in old}
                tags = old + [t for t in tags if tag_key(t) not in keys]
            if trigger:
                tags = [trigger] + [t for t in tags if tag_key(t) != trig_k]
            with open(cap, "w", encoding="utf-8") as f:
                f.write(", ".join(tags))
            done += 1
        progress(done, total, f"Tagged {done}/{total}")
    emit("R", {"tagged": done, "skipped": len(job["images"]) - total})


if __name__ == "__main__":
    main()
