"""
Scriptaz Native Menu Bar & System Tray Desktop Application Runner
Runs quietly in macOS Menu Bar and Windows System Tray, manages active-time scheduler,
and coordinates the Pop-up Card and Control Panel windows.
"""

import sys
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QWidget
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction

from core.db import db
from core.models import UserSettingsModel
from services.scheduler import scheduler
from ui.popup_card import ScripturePopupCard
from ui.settings_dialog import SettingsDialog, PinnedArchiveDialog, HowItWorksDialog
from resources.icons import get_svg_icon, get_tray_icon
from resources.styles import THEMES

ICONS_DIR = Path(__file__).resolve().parent.parent / "resources" / "icons"


def format_countdown(seconds: int) -> str:
    """Formats remaining seconds into a crisp human countdown string."""
    if seconds <= 0:
        return "momentarily"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    elif minutes > 0:
        return f"{minutes}m {secs:02d}s"
    else:
        return f"{secs}s"


class ScriptazTrayApp(QSystemTrayIcon):
    """
    Native macOS & Windows Menu Bar System Tray Application.
    Houses the persistent background cycle, menu actions, and scheduler coordinator.
    """
    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent)
        self.app = app
        self.active_popup: Optional[ScripturePopupCard] = None
        self.settings_dialog: Optional[SettingsDialog] = None
        self.current_status: dict = {}

        self._init_tray_icon()
        self._init_menu()
        self._connect_signals()
        scheduler.start()

    def _init_tray_icon(self):
        tray_icon = get_tray_icon()
        self.setIcon(tray_icon)
        self.setToolTip("Scriptaz — God's Living Word for Your Workday")
        self.show()

    def _init_menu(self):
        settings = db.get_user_settings()
        c = THEMES["dark"] if settings.dark_mode else THEMES["light"]
        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c["bg_card"]};
                border: 1px solid {c["border"]};
                border-radius: 8px;
                padding: 6px;
                font-family: '.AppleSystemUIFont', 'Helvetica Neue', sans-serif;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
                color: {c["text_primary"]};
            }}
            QMenu::item:selected {{
                background-color: {c["chip_active_bg"]};
                color: {c["accent"]};
            }}
            QMenu::separator {{
                height: 1px;
                background: {c["border_subtle"]};
                margin: 4px 8px;
            }}
        """)
        self.tray_menu.aboutToShow.connect(self._on_menu_about_to_show)

        # 1. Status Indicator Header
        self.status_action = QAction("● Active: Calculating countdown...", self.tray_menu)
        self.status_action.setEnabled(False)
        self.tray_menu.addAction(self.status_action)
        self.tray_menu.addSeparator()

        # 2. Quick Actions
        self.trigger_action = QAction("⚡ Show Scripture Now", self.tray_menu)
        self.trigger_action.triggered.connect(self._on_trigger_now)
        self.tray_menu.addAction(self.trigger_action)

        self.settings_action = QAction("⚙️ Control Panel & Preferences", self.tray_menu)
        self.settings_action.triggered.connect(self._open_control_panel)
        self.tray_menu.addAction(self.settings_action)

        self.pinned_action = QAction("📚 My Pinned Verses Archive", self.tray_menu)
        self.pinned_action.triggered.connect(self._open_pinned_archive)
        self.tray_menu.addAction(self.pinned_action)

        self.info_action = QAction("ⓘ How Scriptaz Works", self.tray_menu)
        self.info_action.triggered.connect(self._open_info_guide)
        self.tray_menu.addAction(self.info_action)

        self.tray_menu.addSeparator()

        # 3. Pause / Resume Toggle
        self.pause_action = QAction("⏸️ Pause Workday Tracking", self.tray_menu)
        self.pause_action.triggered.connect(self._toggle_pause)
        self.tray_menu.addAction(self.pause_action)

        self.tray_menu.addSeparator()

        # 4. Quit Action
        self.quit_action = QAction("⏻ Quit Scriptaz", self.tray_menu)
        self.quit_action.triggered.connect(self._on_quit)
        self.tray_menu.addAction(self.quit_action)

        self.setContextMenu(self.tray_menu)

    def _connect_signals(self):
        scheduler.verse_trigger_signal.connect(self._display_scripture_card)
        scheduler.status_updated_signal.connect(self._on_status_updated)

    def _on_menu_about_to_show(self):
        """Immediately refreshes the live countdown before menu displays."""
        curr = scheduler.get_current_status()
        self._on_status_updated(curr)

    def _on_status_updated(self, status: dict):
        self.current_status = status
        state = status.get("state", "Active")
        rem_sec = status.get("remaining_seconds", 0)
        delivered = status.get("verses_delivered_today", 0)
        limit = status.get("daily_limit", 5)
        is_paused = status.get("is_paused", False)
        is_idle = status.get("is_idle", False)
        cycle = status.get("current_cycle", 1)

        countdown = format_countdown(rem_sec)
        progress = f"{delivered}/{limit} today" if cycle == 1 else f"{delivered}/{limit} • Cycle {cycle}"

        if is_paused:
            self.status_action.setText(f"⏸ Paused: Next verse in {countdown} ({progress})")
            self.pause_action.setText("▶️ Resume Workday Tracking")
        elif is_idle:
            self.status_action.setText(f"🌙 Away: Next verse in {countdown} (paused while away)")
            self.pause_action.setText("⏸️ Pause Workday Tracking")
        else:
            self.status_action.setText(f"● Active: Next verse in {countdown} ({progress})")
            self.pause_action.setText("⏸️ Pause Workday Tracking")

    def _display_scripture_card(self, verse_data: dict):
        """Pops up the centered floating scripture card."""
        if self.active_popup:
            self.active_popup.close()

        self.active_popup = ScripturePopupCard(verse_data)
        self.active_popup.show()
        self.active_popup.raise_()
        self.active_popup.activateWindow()

    def _on_trigger_now(self):
        scheduler.trigger_now()

    def _toggle_pause(self):
        is_paused = self.current_status.get("is_paused", False)
        scheduler.set_paused(not is_paused)

    def _open_control_panel(self):
        self.settings_dialog = SettingsDialog(is_welcome_mode=False)
        self.settings_dialog.settings_saved.connect(lambda _: self._on_settings_reloaded())
        self.settings_dialog.exec()

    def _on_settings_reloaded(self):
        scheduler.reload_settings()
        self._init_tray_icon()
        self._init_menu()

    def _open_pinned_archive(self):
        settings = db.get_user_settings()
        dlg = PinnedArchiveDialog(is_dark=settings.dark_mode, parent=None)
        dlg.exec()

    def _open_info_guide(self):
        settings = db.get_user_settings()
        dlg = HowItWorksDialog(is_dark=settings.dark_mode, parent=None)
        dlg.exec()

    def check_first_launch(self):
        """If user settings haven't been customized, launches Welcome Mode."""
        settings = db.get_user_settings()
        if not settings.user_name:
            # Show welcome setup dialog
            self.settings_dialog = SettingsDialog(is_welcome_mode=True)
            self.settings_dialog.settings_saved.connect(lambda _: self._on_settings_reloaded())
            self.settings_dialog.exec()

    def _on_quit(self):
        self.app.quit()
