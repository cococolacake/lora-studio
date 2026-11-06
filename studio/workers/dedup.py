"""Find near-duplicate images with CLIP ViT-B/32.
Doesn't move anything: returns groups so you can review them first.

job: {folder, recursive, threshold, skip_dirs: [...]}
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, is_image, load_job, natural_key, need, progress  # noqa: E402


def main():
    job = load_job()
    torch, transformers, PIL = need("torch", "transformers", "PIL")
    from PIL import Image
    from transformers import AutoProcessor, CLIPVisionModelWithProjection

    skip = set(job.get("skip_dirs") or ["_duplicates", "_originals"])
    folders = []
    for cur, dirs, files in os.walk(job["folder"]):
        dirs[:] = [d for d in dirs if d not in skip]
        imgs = sorted([os.path.join(cur, f) for f in files if is_image(f)], key=natural_key)
        if imgs:
            folders.append(imgs)
        if not job.get("recursive"):
            break
    total = sum(len(f) for f in folders)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    progress(0, total, f"Loading CLIP on {dev}...")
    model = CLIPVisionModelWithProjection.from_pretrained("openai/clip-vit-base-patch32").to(dev).eval()
    proc = AutoProcessor.from_pretrained("openai/clip-vit-base-patch32")
    thr = float(job.get("threshold", 0.92))
    groups, done = [], 0
    for imgs in folders:
        paths, feats = [], []
        for i in range(0, len(imgs), 32):
            batch = []
            for p in imgs[i:i + 32]:
                try:
                    with Image.open(p) as im:
                        batch.append(im.convert("RGB"))
                    paths.append(p)
                except Exception as e:
                    sys.stdout.write(f"Skipping {os.path.basename(p)}: {e}\n")
            done += len(imgs[i:i + 32])
            if not batch:
                continue
            inputs = proc(images=batch, return_tensors="pt").to(dev)
            with torch.no_grad():
                f = model(**inputs).image_embeds.float()
            feats.append(f / f.norm(dim=-1, keepdim=True))
            progress(done, total, f"Embedded {done}/{total}")
        if not feats:
            continue
        sim = (torch.cat(feats) @ torch.cat(feats).T).cpu()
        taken = set()
        for i in range(len(paths)):
            if i in taken:
                continue
            members = []
            for j in range(i + 1, len(paths)):
                if j in taken:
                    continue
                s = float(sim[i][j])
                if s >= thr:
                    members.append({"path": paths[j], "score": round(s, 4)})
                    taken.add(j)
            if members:
                groups.append({"keep": paths[i], "dupes": members})
    emit("R", {"groups": groups, "scanned": total})


if __name__ == "__main__":
    main()
