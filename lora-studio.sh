#!/usr/bin/env bash
# Start LoRA Studio on Linux.  ./lora-studio.sh            app window
#                              ./lora-studio.sh --browser  open in your web browser
#                              ./lora-studio.sh --debug    app window with dev tools
cd "$(dirname "$(readlink -f "$0")")"
if [ ! -x .venv/bin/python ]; then
  echo "LoRA Studio isn't set up yet. Run ./install.sh first."
  exit 1
fi
exec .venv/bin/python main.py "$@"
