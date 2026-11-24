# Datasets

Everything on the **Dataset** page.

## New dataset in one click

Download with **gallery-dl** (Danbooru, Gelbooru, e621, pixiv and hundreds more), skip tiny images, number everything, turn the site's tags into captions, and check for duplicates. Site logins and API keys are stored on your PC only.

### Downloading with gallery-dl

Dataset → **New dataset** → **Install gallery-dl** (one time). Pick a site and type tags, or paste any link gallery-dl supports.

- **Site logins:** sites that need a login or API key are set up under **Site logins**.
- **pixiv:** press **Get token** and follow the window that opens.
- **Other logged-in sites:** gallery-dl can use your browser's cookies; Firefox works best.

Downloads go to the `downloads` folder in LoRA Studio's data folder (`%APPDATA%\LoRA Studio` on Windows, `~/.local/share/lora-studio` on Linux) unless you pick a folder.

## The tools

- **Images & tags:** caption editor with tag chips, autocomplete, filters, keyboard shortcuts and bulk add/remove/replace with undo. The **tag overview** shows every tag by how often it's used (sort by rarest to spot typos), and renames or removes it everywhere.
- **Auto-tagging:** with the WD EVA02 tagger.
- **Crop & resize:** a Photos-style crop window, plus batch resize to a long side, short side or exact size (e.g. 1024×1024, 832×1216). Originals are always kept.
- **Duplicates:** finds look-alike images with CLIP; you review before anything moves, then delete them for good with one click.
- **Health check:** catches missing/empty captions, unreadable images, caption clashes, missing trigger words and odd sizes, and estimates buckets and steps.
- **Rename:** numbered names with a preview first.

## Folders LoRA Studio creates in your dataset

- `_originals/` keeps the original of any image you crop or resize.
- `_deleted/` holds images deleted in the viewer, with their captions. You can restore them.
- `_duplicates/` holds images moved by the duplicate finder.

sd-scripts ignores all three folders.
