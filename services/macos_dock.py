"""
Native macOS AppKit & LaunchAgent Integration for Scriptaz
Handles:
1. Dynamic Dock visibility (hiding from Dock during background mode, showing during card display).
2. Mission Control / Full-Screen / Spaces Intervention (ensuring scripture cards float above full-screen games, IDEs, and all spaces).
3. macOS LaunchAgent management for continuous auto-start on login.
"""

import sys
import os
import plistlib
from pathlib import Path
from typing import Optional

PLIST_NAME = "com.scriptaz.app.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / PLIST_NAME


def is_macos() -> bool:
    return sys.platform == "darwin"


def set_dock_icon_visible(visible: bool):
    """Dynamically shows or hides the Scriptaz icon in the macOS Dock."""
    if not is_macos():
        return
    try:
        from AppKit import (
            NSApplication,
            NSApplicationActivationPolicyRegular,
            NSApplicationActivationPolicyAccessory,
        )
        app = NSApplication.sharedApplication()
        if visible:
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        else:
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception as e:
        # Fallback if AppKit is unavailable
        pass


def make_window_stay_on_top_all_spaces(win_id: int):
    """
    Configures a native NSWindow to appear on top of all macOS Spaces,
    full-screen applications, video players, and games.
    """
    if not is_macos():
        return
    try:
        import objc
        from AppKit import (
            NSApplication,
            NSFloatingWindowLevel,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
        )

        app = NSApplication.sharedApplication()
        
        # Find matching NSWindow by windowNumber
        target_window = None
        for window in app.windows():
            if window.windowNumber() == win_id:
                target_window = window
                break

        if target_window:
            # Join all spaces + auxiliary over full-screen apps & games
            behavior = (
                NSWindowCollectionBehaviorCanJoinAllSpaces |
                NSWindowCollectionBehaviorFullScreenAuxiliary
            )
            target_window.setCollectionBehavior_(behavior)
            target_window.setLevel_(NSFloatingWindowLevel)
            target_window.orderFrontRegardless()

        # Force app to the front regardless of current full-screen app
        app.activateIgnoringOtherApps_(True)
    except Exception as e:
        pass


def set_launch_on_startup(enabled: bool, app_path: Optional[str] = None):
    """Enables or disables automatic launch on macOS login via LaunchAgent."""
    if not is_macos():
        return

    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    if not enabled:
        if PLIST_PATH.exists():
            try:
                PLIST_PATH.unlink()
            except Exception:
                pass
        return

    # Determine app executable path
    exec_path = app_path
    if not exec_path:
        default_app = Path("/Applications/Scriptaz.app/Contents/MacOS/Scriptaz")
        if default_app.exists():
            exec_path = str(default_app)
        else:
            exec_path = sys.executable

    plist_data = {
        "Label": "com.scriptaz.app",
        "ProgramArguments": [str(exec_path)],
        "RunAtLoad": True,
        "KeepAlive": False,
        "ProcessType": "Interactive"
    }

    try:
        with open(PLIST_PATH, "wb") as fp:
            plistlib.dump(plist_data, fp)
    except Exception as e:
        print(f"Warning: Could not save LaunchAgent plist: {e}")
