"""Desktop notifications when a training finishes, with no extra Python packages.

Windows: Windows PowerShell's built-in WinRT access. Shown under "Windows PowerShell" as the sender,
         because Windows only allows registered apps to post notifications under their own name.
Linux:   the standard notify-send command (package libnotify-bin / libnotify on most distros).
"""
import base64
import os
import shutil
import subprocess
from xml.sax.saxutils import escape

from . import settings
from .util import CREATE_NO_WINDOW

APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(@'
__XML__
'@)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('__APP__').Show($toast)
"""


ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "assets", "icon-512.png")


def unavailable_reason():
    if not settings.get("notify_on_finish"):
        return "Notifications are turned off. Switch them on first."
    if os.name != "nt" and not shutil.which("notify-send"):
        return "notify-send wasn't found. Install it (e.g. sudo apt install libnotify-bin) and try again."
    return "Notifications aren't available on this system."


def toast(title, body=""):
    """Show a desktop notification. Returns False if it couldn't or if turned off in Settings."""
    if not settings.get("notify_on_finish"):
        return False
    if os.name != "nt":
        return _notify_send(title, body)
    xml = ('<toast><visual><binding template="ToastGeneric">'
           f"<text>{escape(title)}</text><text>{escape(body)}</text>"
           '</binding></visual><audio src="ms-winsoundevent:Notification.Default"/></toast>')
    script = SCRIPT.replace("__XML__", xml).replace("__APP__", APP_ID)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    try:
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                         creationflags=CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def _notify_send(title, body):
    exe = shutil.which("notify-send")
    if not exe:
        return False
    try:
        subprocess.Popen([exe, "--app-name=LoRA Studio", f"--icon={ICON}", title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False
