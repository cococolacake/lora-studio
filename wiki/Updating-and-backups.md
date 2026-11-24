# Updating and backups

## Updating

**The easy way:** when a new version is out, a small download button with a dot appears in LoRA Studio's sidebar (and in **Settings → About**). Click **Update now**: LoRA Studio downloads the new version, keeps your `.venv`, your `custom.css` and all your settings, runs and presets, installs anything new, and restarts with one click.

**By hand:** download the new zip from [Releases](https://github.com/cococolacake/lora-studio/releases/latest) and unzip it over your LoRA Studio folder (keep the `.venv` folder), or **Pull** in GitHub Desktop / `git pull` if you cloned it. Then start LoRA Studio as usual.

What changed in each version is on the [Releases](https://github.com/cococolacake/lora-studio/releases) page.

## sd-scripts

The **sd-scripts** page updates sd-scripts, switches its branch, or rolls it back.

## Backup & restore

Settings → **Folders & backup** → **Create backup** saves your settings, presets, themes and run history in one zip. Your datasets, trained LoRAs and site logins aren't included.
