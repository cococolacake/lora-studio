# Security

## Reporting a problem

Please **don't** open a public issue for security problems. Report them privately instead:
[open a security advisory](https://github.com/cococolacake/lora-studio/security/advisories/new) on GitHub.

Include what you found, how to reproduce it, and which version you're on (Settings → About).
I'll reply as soon as I can, and credit you in the fix if you'd like.

## What LoRA Studio keeps where

- **Site logins and API keys** for gallery-dl (Danbooru, e621, pixiv and so on) are stored only in
  `gallery-dl.json` in LoRA Studio's data folder on your computer. They're left out of backups and
  out of **Copy diagnostics**.
- **The app** listens only on your own computer (127.0.0.1), and only its own page may call it.
- **Copy diagnostics** masks your home folder (it usually contains your name) and leaves out site logins.
- **Shared presets** leave out your own paths.
- **Updates** come only from this repository on GitHub (its releases, or `git pull` if you cloned it).

## Supported versions

Only the latest release gets fixes.
