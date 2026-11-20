"""Windows shortcuts that pin to the taskbar properly.

The app window tells Windows it is "LoRAStudio.App" (see main.py). For a pinned
taskbar button to start LoRA Studio again, Windows also needs a shortcut that
carries the same app ID, so it knows which command to run. A plain shortcut
(or the .bat file) has no ID, so Windows pinned python.exe instead, and the pin
opened a second, separate window.

make() writes the Start menu shortcut (and, if asked, a desktop one) and stamps
the app ID on it. It is quiet on failure: the app works the same without it.
"""
import base64
import os
import subprocess
import sys
from pathlib import Path

APP_ID = "LoRAStudio.App"
NAME = "LoRA Studio"

ROOT = Path(__file__).resolve().parent.parent

# Sets System.AppUserModel.ID on a .lnk file. Windows has no PowerShell command
# for it, so this small C# helper does it through the shell's property store.
_CS = r'''
using System;
using System.Runtime.InteropServices;
public static class LoraStudioLnk {
  [StructLayout(LayoutKind.Sequential, Pack = 4)]
  public struct PROPERTYKEY { public Guid fmtid; public uint pid; }
  [StructLayout(LayoutKind.Explicit)]
  public struct PROPVARIANT { [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public IntPtr p; [FieldOffset(16)] public IntPtr p2; }
  [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  public interface IPropertyStore {
    [PreserveSig] int GetCount(out uint c);
    [PreserveSig] int GetAt(uint i, out PROPERTYKEY k);
    [PreserveSig] int GetValue(ref PROPERTYKEY k, out PROPVARIANT v);
    [PreserveSig] int SetValue(ref PROPERTYKEY k, ref PROPVARIANT v);
    [PreserveSig] int Commit();
  }
  [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
  static extern void SHGetPropertyStoreFromParsingName(string path, IntPtr pbc, int flags, ref Guid iid,
    [MarshalAs(UnmanagedType.Interface)] out IPropertyStore store);
  public static void SetAppId(string lnk, string id) {
    Guid iid = typeof(IPropertyStore).GUID;
    IPropertyStore st;
    SHGetPropertyStoreFromParsingName(lnk, IntPtr.Zero, 2, ref iid, out st);   // 2 = read/write
    var key = new PROPERTYKEY { fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid = 5 };
    var pv = new PROPVARIANT { vt = 31, p = Marshal.StringToCoTaskMemUni(id) };   // 31 = VT_LPWSTR
    try {
      int hr = st.SetValue(ref key, ref pv); if (hr != 0) Marshal.ThrowExceptionForHR(hr);
      hr = st.Commit(); if (hr != 0) Marshal.ThrowExceptionForHR(hr);
    } finally { Marshal.FreeCoTaskMem(pv.p); Marshal.ReleaseComObject(st); }
  }
}
'''

_PS = r'''
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition $env:LS_CS
$sh = New-Object -ComObject WScript.Shell
foreach ($p in $env:LS_LNKS.Split('|')) {
  $d = Split-Path $p
  if (!(Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
  $s = $sh.CreateShortcut($p)
  $s.TargetPath = $env:LS_TARGET
  $s.Arguments = $env:LS_ARGS
  $s.WorkingDirectory = $env:LS_DIR
  $s.IconLocation = $env:LS_ICON
  $s.Description = 'LoRA Studio'
  $s.Save()
  [LoraStudioLnk]::SetAppId($p, $env:LS_APPID)
}
'''


def start_menu_path():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{NAME}.lnk"


def desktop_path():
    return Path(os.path.expanduser("~")) / "Desktop" / f"{NAME}.lnk"


def _pythonw():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def make(start_menu=True, desktop=False):
    """Write the shortcuts. Returns the paths written, or [] if this isn't Windows or it failed."""
    if os.name != "nt":
        return []
    lnks = [p for p, want in ((start_menu_path(), start_menu), (desktop_path(), desktop)) if want]
    if not lnks:
        return []
    env = {**os.environ,
           "LS_CS": _CS, "LS_LNKS": "|".join(str(p) for p in lnks), "LS_TARGET": str(_pythonw()),
           "LS_ARGS": f'"{ROOT / "main.py"}"', "LS_DIR": str(ROOT),
           "LS_ICON": str(ROOT / "web" / "assets" / "icon.ico"), "LS_APPID": APP_ID}
    cmd = base64.b64encode(_PS.encode("utf-16-le")).decode()
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", cmd],
                       env=env, capture_output=True, timeout=60, check=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return lnks
    except Exception:
        return []


def ensure_start_menu():
    """Called when the app starts: add the Start menu shortcut once, if it's missing."""
    if os.name == "nt" and not start_menu_path().exists():
        make(start_menu=True)


if __name__ == "__main__":
    # "Create desktop shortcut.bat" runs this: a desktop shortcut plus the Start menu one.
    made = make(start_menu=True, desktop=True)
    print("Shortcuts created:\n  " + "\n  ".join(map(str, made)) if made else "Couldn't create the shortcuts.")
