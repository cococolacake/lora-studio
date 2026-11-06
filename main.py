"""LoRA Studio — a friendly front end for kohya-ss/sd-scripts.

    python main.py            open the app window
    python main.py --browser  open in your web browser instead (no pywebview needed)
    python main.py --debug    app window with developer tools (right-click > Inspect)
"""
import argparse
import os
import sys
import webbrowser

if sys.version_info < (3, 10):
    sys.exit("LoRA Studio needs Python 3.10 or newer.")

from studio.api import Api


ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "assets", "icon.ico")


def _windows_icon(title):
    """Show the LoRA Studio face in the title bar and taskbar instead of Python's icon."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return
        for size, which in ((16, 0), (32, 1)):   # ICON_SMALL, ICON_BIG
            hicon = user32.LoadImageW(None, ICON, 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if hicon:
                user32.SendMessageW(hwnd, 0x80, which, hicon)           # WM_SETICON
    except Exception:
        pass


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # so web/index.html resolves
    if os.name == "nt":
        try:  # group under our own taskbar entry (with our icon), not under python.exe
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LoRAStudio.App")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="LoRA Studio")
    ap.add_argument("--browser", action="store_true", help="open in the default web browser")
    ap.add_argument("--port", type=int, default=0, help="port for --browser mode")
    ap.add_argument("--debug", action="store_true", help="enable dev tools in the app window")
    args = ap.parse_args()

    api = Api()

    if not args.browser:
        try:
            import webview
        except ImportError:
            print("pywebview isn't installed, so opening in your browser instead.\n"
                  "Install it with:  pip install pywebview")
            args.browser = True

    if args.browser:
        from studio.devserver import serve
        server, url = serve(api, args.port, background=True)
        print(f"LoRA Studio: {url}  (Ctrl+C to quit)")
        webbrowser.open(url)
        try:
            import threading
            threading.Event().wait()   # the server already runs in the background
        except KeyboardInterrupt:
            pass
        finally:
            api._trainer.stop_current()
        return

    # Serve the UI ourselves (no caching, so updates always show up) on a fixed port,
    # so the window's saved state (drafts, view settings) survives restarts.
    from studio.devserver import serve
    try:
        server, url = serve(api, 42011, background=True)
    except OSError:
        server, url = serve(api, 0, background=True)

    window = webview.create_window(
        "LoRA Studio", url, js_api=api,
        width=1400, height=900, min_size=(1100, 700), background_color="#F4F4F5",
    )
    api._attach_window(window)
    if os.name == "nt":
        window.events.shown += lambda: _windows_icon("LoRA Studio")
    webview.start(debug=args.debug, private_mode=False)
    # Window closed: don't leave a training process running in the background.
    api._trainer.stop_current()


if __name__ == "__main__":
    sys.exit(main())
