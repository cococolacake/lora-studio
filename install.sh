#!/usr/bin/env bash
# LoRA Studio setup for Linux. Run once:  ./install.sh
# Makes a private Python environment (.venv) in this folder and installs LoRA Studio's small
# dependencies. Training itself runs in your sd-scripts venv, so no torch is installed here.
#
# The app window needs GTK or Qt:
#   - If your system already has GTK + WebKit for Python (most GNOME desktops), that's used.
#   - Otherwise Qt is installed with pip (a bigger download, but no system packages needed).
#   - Force one with:  ./install.sh --gtk   or   ./install.sh --qt
#   - Or skip both with  ./install.sh --browser  and LoRA Studio opens in your web browser.
set -e
cd "$(dirname "$0")"

MODE="auto"
case "$1" in
  --gtk) MODE="gtk" ;;
  --qt) MODE="qt" ;;
  --browser) MODE="browser" ;;
  "") ;;
  *) echo "Unknown option: $1  (use --gtk, --qt or --browser)"; exit 1 ;;
esac

echo
echo " Setting up LoRA Studio..."
echo

PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    PY="$cand"; break
  fi
done
if [ -z "$PY" ]; then
  echo " Python 3.10 or newer wasn't found. Install it with your package manager, e.g."
  echo "   sudo apt install python3 python3-venv      (Debian/Ubuntu)"
  echo "   sudo dnf install python3                   (Fedora)"
  echo "   sudo pacman -S python                      (Arch)"
  exit 1
fi

has_gtk() {
  "$PY" - <<'EOF' 2>/dev/null
import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, WebKit2
EOF
}

if [ "$MODE" = "auto" ]; then
  if has_gtk; then MODE="gtk"; else MODE="qt"; fi
fi
if [ "$MODE" = "gtk" ] && ! has_gtk; then
  echo " GTK + WebKit for Python wasn't found. Install it, e.g."
  echo "   sudo apt install python3-gi gir1.2-webkit2-4.1        (Debian/Ubuntu)"
  echo "   sudo dnf install python3-gobject webkit2gtk4.1        (Fedora)"
  echo "   sudo pacman -S python-gobject webkit2gtk-4.1          (Arch)"
  echo " ...or run  ./install.sh --qt  instead."
  exit 1
fi

# GTK comes from the system, so the venv needs to see system packages for it.
VENV_ARGS=""
[ "$MODE" = "gtk" ] && VENV_ARGS="--system-site-packages"

if [ -d .venv ] && [ -f .venv/.window_toolkit ] && [ "$(cat .venv/.window_toolkit)" != "$MODE" ]; then
  echo " Switching the app window to $MODE, rebuilding .venv..."
  rm -rf .venv
fi
if [ ! -x .venv/bin/python ]; then
  if ! "$PY" -m venv $VENV_ARGS .venv; then
    echo
    echo " Couldn't create the environment. On Debian/Ubuntu install the venv package:"
    echo "   sudo apt install python3-venv"
    exit 1
  fi
fi
echo "$MODE" > .venv/.window_toolkit

.venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1 || true
if ! .venv/bin/python -m pip install -r requirements.txt; then
  echo
  echo " Setup failed while downloading packages. Check your internet connection and run ./install.sh again."
  exit 1
fi

if [ "$MODE" = "qt" ]; then
  echo
  echo " Installing Qt for the app window (this one is a bigger download)..."
  if ! .venv/bin/python -m pip install "pywebview[qt]"; then
    echo
    echo " Qt couldn't be installed, so LoRA Studio will open in your web browser instead."
    echo " (Everything still works; only the native file pickers are missing.)"
  fi
fi

chmod +x lora-studio.sh create-desktop-entry.sh 2>/dev/null || true

echo
echo " All done! Start LoRA Studio with:  ./lora-studio.sh"
echo " Want it in your app menu? Run:      ./create-desktop-entry.sh"
echo
if ! command -v notify-send >/dev/null 2>&1; then
  echo " Tip: for 'training finished' notifications, install notify-send"
  echo "      (sudo apt install libnotify-bin, or libnotify on Fedora/Arch)."
  echo
fi
