"""
Scriptaz — God's Living Word for Your Active Workday
Native Desktop Application Entry Point (macOS & Windows)
"""

import sys
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config
from core.db import db
from ui.tray_app import ScriptazTrayApp
from ui.popup_card import ScripturePopupCard
from ui.settings_dialog import SettingsDialog, HowItWorksDialog


def run_app():
    parser = argparse.ArgumentParser(description="Scriptaz Desktop Application")
    parser.add_argument("--welcome", action="store_true", help="Launch Welcome Setup Dialog")
    parser.add_argument("--settings", action="store_true", help="Launch Control Panel directly")
    parser.add_argument("--popup", action="store_true", help="Show a test scripture pop-up card")
    parser.add_argument("--guide", action="store_true", help="Launch How It Works Guide directly")
    args = parser.parse_args()

    # Enable High-DPI Scaling for Retina / 4K Displays
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Scriptaz")
    app.setOrganizationName("Scriptaz")
    app.setQuitOnLastWindowClosed(False)   # Keep running silently in Menu Bar / System Tray

    # Set App Icon
    app_icon_path = ROOT_DIR / "resources" / "icons" / "app_icon.png"
    if app_icon_path.exists():
        app.setWindowIcon(QIcon(str(app_icon_path)))

    if args.guide:
        app.setQuitOnLastWindowClosed(True)
        settings = db.get_user_settings()
        dlg = HowItWorksDialog(is_dark=settings.dark_mode)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        sys.exit(app.exec())

    if args.popup:
        app.setQuitOnLastWindowClosed(True)
        settings = db.get_user_settings()
        verse_data = db.get_next_verse_for_user(
            theme=settings.active_theme,
            translation=settings.active_translation
        )
        if not verse_data:
            verse_data = {
                "reference": "Philippians 4:6-7",
                "translation": "NKJV",
                "text": "Be anxious for nothing, but in everything by prayer and supplication, with thanksgiving, let your requests be made known to God; and the peace of God, which surpasses all understanding, will guard your hearts and minds through Christ Jesus.",
                "theme": "Peace"
            }
        card = ScripturePopupCard(verse_data)
        card.show()
        card.raise_()
        card.activateWindow()
        sys.exit(app.exec())

    if args.settings:
        app.setQuitOnLastWindowClosed(True)
        dialog = SettingsDialog(is_welcome_mode=False)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        sys.exit(app.exec())

    if args.welcome:
        app.setQuitOnLastWindowClosed(True)
        dialog = SettingsDialog(is_welcome_mode=True)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        sys.exit(app.exec())

    # Standard Daemon Mode (Menu Bar / System Tray Runner)
    from services.macos_dock import set_dock_icon_visible, set_launch_on_startup
    settings = db.get_user_settings()

    # If background mode is enabled, hide from Dock immediately on launch
    if settings.run_in_background:
        set_dock_icon_visible(False)

    # Sync startup LaunchAgent
    if settings.launch_on_startup:
        set_launch_on_startup(True)

    tray = ScriptazTrayApp(app)

    # First-Launch Detection: Only show Welcome Panel if onboarding has NEVER been completed!
    if not settings.has_completed_onboarding:
        set_dock_icon_visible(True)
        welcome_dialog = SettingsDialog(is_welcome_mode=True)
        welcome_dialog.settings_saved.connect(lambda _: tray._on_settings_reloaded())
        welcome_dialog.show()
        welcome_dialog.raise_()
        welcome_dialog.activateWindow()

    print("✨ Scriptaz is running quietly in your Menu Bar / System Tray.")
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
