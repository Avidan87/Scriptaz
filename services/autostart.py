"""
Scriptaz Cross-Platform Auto-Start Service Engine
Manages silent Launch on Startup for macOS (LaunchAgent) and Windows (Registry Run Key).
"""

import os
import sys
import platform
from pathlib import Path

LAUNCH_AGENT_LABEL = "com.avidan.scriptaz"


def get_macos_plist_path() -> Path:
    """Returns path to the user's macOS LaunchAgent plist."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def is_autostart_enabled() -> bool:
    """Checks if autostart is currently enabled on macOS or Windows."""
    system = platform.system()

    if system == "Darwin":
        plist = get_macos_plist_path()
        return plist.exists()

    elif system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ
            )
            val, _ = winreg.QueryValueEx(key, "Scriptaz")
            winreg.CloseKey(key)
            return bool(val)
        except Exception:
            return False

    return False


def set_autostart_enabled(enabled: bool) -> bool:
    """Enables or disables autostart on system boot."""
    system = platform.system()
    python_exe = sys.executable
    main_script = str(Path(__file__).resolve().parent.parent / "main.py")

    if system == "Darwin":
        plist_path = get_macos_plist_path()
        if enabled:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{main_script}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
            with open(plist_path, "w", encoding="utf-8") as f:
                f.write(plist_content)
            return True
        else:
            if plist_path.exists():
                plist_path.unlink()
            return True

    elif system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            if enabled:
                cmd = f'"{python_exe}" "{main_script}"'
                winreg.SetValueEx(key, "Scriptaz", 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, "Scriptaz")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Windows autostart error: {e}")
            return False

    return False
