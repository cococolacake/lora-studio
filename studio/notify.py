"""Windows notifications (the pop-ups in the bottom-right corner), with no extra packages.

Uses Windows PowerShell's built-in WinRT access. Shown under "Windows PowerShell" as the sender,
because Windows only allows registered apps to post notifications under their own name.
"""
import base64
import os
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


def toast(title, body=""):
    """Show a Windows notification. Does nothing on other systems or if turned off in Settings."""
    if os.name != "nt" or not settings.get("notify_on_finish"):
        return False
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
