"""
Scriptaz Floating Scripture Pop-up Card
Native macOS window with real OS title bar (🔴 🟡 🟢), crisp vector SVG icons (no emojis),
Light / Dark mode support, generous dimensions (640x360px), dynamic typography,
and live 1-click Pinning toggle.
"""

import sys
from typing import Optional, Dict
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QTextBrowser,
    QPushButton, QFrame, QApplication
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QScreen, QCursor, QIcon

from core.db import db
from core.models import UserSettingsModel, BibleTranslation, ScriptureTheme
from resources.styles import get_popup_qss, format_scripture_html, THEMES
from resources.icons import get_svg_icon
from services.macos_dock import set_dock_icon_visible, make_window_stay_on_top_all_spaces

CARD_WIDTH = 640
CARD_HEIGHT = 360
TRANSLATIONS = ["KJV", "NKJV", "ESV", "NLT"]


def format_theme_badge_text(title: str, max_chars: int = 24) -> str:
    """
    Intelligently truncates theme titles at clean word boundaries
    without chopping words in half, and strips hanging conjunctions.
    """
    title = title.strip()
    if len(title) <= max_chars:
        return title.upper()
    truncated = title[:max_chars].rsplit(" ", 1)[0]
    if not truncated:
        truncated = title[:max_chars]
    hanging = ["AND", "OR", "OF", "IN", "THE", "FOR", "WITH", "A", "AN", "&"]
    words = truncated.split()
    while words and words[-1].upper() in hanging:
        words.pop()
    clean = " ".join(words).rstrip(" ,.-:;")
    return (clean.upper() if clean else truncated.upper()) + "..."


class ScripturePopupCard(QWidget):
    """Floating, centered, stays-on-top Scripture Pop-up Window."""

    def __init__(self, verse_data: Dict, parent=None):
        super().__init__(parent)
        self.verse_data = verse_data
        self.settings: UserSettingsModel = db.get_user_settings()
        self.is_dark = self.settings.dark_mode
        self.current_trans = self.verse_data.get("translation", "NKJV")
        self.verse_id = self.verse_data.get("id")
        self.is_pinned = db.is_verse_pinned(self.verse_id) if self.verse_id else False

        self._init_window_properties()
        self._init_ui()
        self._center_on_screen()

    def _init_window_properties(self):
        self.setWindowTitle("Scriptaz")
        self.setObjectName("PopupCardRoot")
        self.resize(CARD_WIDTH, CARD_HEIGHT)
        self.setMinimumSize(540, 300)
        self.setStyleSheet(get_popup_qss(self.is_dark))
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

    def showEvent(self, event):
        super().showEvent(event)
        if self.settings.run_in_background:
            set_dock_icon_visible(True)
        make_window_stay_on_top_all_spaces(int(self.winId()))
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        super().closeEvent(event)
        if self.settings.run_in_background:
            set_dock_icon_visible(False)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + (geom.height() - self.height()) // 2
            self.move(x, y)

    def _init_ui(self):
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(28, 22, 28, 22)
        card_layout.setSpacing(14)

        # -------------------------------------------------------------
        # 1. Top Badges Row (Theme Badge + Translation Badge)
        # -------------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(8)

        # Theme Badge
        raw_theme = self.verse_data.get("theme", "")
        is_custom = (self.settings.active_theme == ScriptureTheme.CUSTOM or str(self.settings.active_theme.value).lower() == "custom")
        if is_custom and self.settings.active_custom_theme_title:
            full_theme_title = self.settings.active_custom_theme_title
        elif raw_theme:
            full_theme_title = raw_theme
        else:
            full_theme_title = self.settings.active_theme.value if hasattr(self.settings.active_theme, 'value') else str(self.settings.active_theme)

        badge_text = format_theme_badge_text(full_theme_title, max_chars=24)
        self.theme_badge = QLabel(badge_text)
        self.theme_badge.setToolTip(full_theme_title)
        self.theme_badge.setObjectName("ThemeBadge")
        header.addWidget(self.theme_badge)

        header.addStretch()

        # Translation Badge
        self.trans_badge = QLabel(self.current_trans)
        self.trans_badge.setObjectName("TranslationBadge")
        header.addWidget(self.trans_badge)

        card_layout.addLayout(header)

        # -------------------------------------------------------------
        # 2. Scripture Reference & Text
        # -------------------------------------------------------------
        self.ref_label = QLabel(self.verse_data.get("reference", "Philippians 4:6–7"))
        self.ref_label.setObjectName("ScriptureReference")
        card_layout.addWidget(self.ref_label)

        self.text_browser = QTextBrowser()
        self.text_browser.setObjectName("ScriptureText")
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_browser.viewport().setStyleSheet("background: transparent;")
        c = THEMES["dark"] if self.is_dark else THEMES["light"]
        self.text_browser.setStyleSheet(f"background: transparent; border: none; color: {c['text_primary']};")
        self._update_scripture_html()
        card_layout.addWidget(self.text_browser, 1)

        # -------------------------------------------------------------
        # 3. Bottom Action Row (Pin Toggle + Translation Cycle with Vector Icons)
        # -------------------------------------------------------------
        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        # Pin / Unpin Button with Vector SVG Icon
        self.pin_btn = QPushButton()
        self.pin_btn.setIconSize(QSize(15, 15))
        self.pin_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.pin_btn.clicked.connect(self._toggle_pin)
        self._update_pin_ui()
        action_row.addWidget(self.pin_btn)

        # Translation Switcher Button with Vector Refresh SVG Icon
        self.cycle_trans_btn = QPushButton(f" {self.current_trans}")
        self.cycle_trans_btn.setObjectName("TransCycleBtn")
        refresh_icon_color = THEMES["dark"]["text_secondary"] if self.is_dark else THEMES["light"]["text_secondary"]
        self.cycle_trans_btn.setIcon(get_svg_icon("refresh", color=refresh_icon_color, size=15))
        self.cycle_trans_btn.setIconSize(QSize(15, 15))
        self.cycle_trans_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.cycle_trans_btn.clicked.connect(self._cycle_translation)
        action_row.addWidget(self.cycle_trans_btn)

        action_row.addStretch()

        # Dismiss Button
        self.dismiss_btn = QPushButton("Dismiss")
        self.dismiss_btn.setObjectName("DismissBtn")
        self.dismiss_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.dismiss_btn.clicked.connect(self.close)
        action_row.addWidget(self.dismiss_btn)

        card_layout.addLayout(action_row)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _update_scripture_html(self):
        text = self.verse_data.get("text", "")
        ref = self.verse_data.get("reference", "")
        formatted_html = format_scripture_html(text=text, reference=ref, is_dark=self.is_dark)
        self.text_browser.setHtml(formatted_html)

    def _update_pin_ui(self):
        accent_color = THEMES["dark"]["accent"] if self.is_dark else THEMES["light"]["accent"]
        muted_color = THEMES["dark"]["text_secondary"] if self.is_dark else THEMES["light"]["text_secondary"]

        if self.is_pinned:
            self.pin_btn.setText(" Pinned")
            self.pin_btn.setObjectName("PinButtonActive")
            self.pin_btn.setIcon(get_svg_icon("check", color=accent_color, size=15))
        else:
            self.pin_btn.setText(" Pin Verse")
            self.pin_btn.setObjectName("PinButton")
            self.pin_btn.setIcon(get_svg_icon("pin", color=muted_color, size=15))
        
        self.pin_btn.style().unpolish(self.pin_btn)
        self.pin_btn.style().polish(self.pin_btn)
        self.pin_btn.update()

    def _toggle_pin(self):
        if not self.verse_id:
            return

        if self.is_pinned:
            db.unpin_verse(self.verse_id)
            self.is_pinned = False
        else:
            db.pin_verse(self.verse_id)
            self.is_pinned = True

        self._update_pin_ui()

    def _cycle_translation(self):
        idx = TRANSLATIONS.index(self.current_trans) if self.current_trans in TRANSLATIONS else 0
        next_idx = (idx + 1) % len(TRANSLATIONS)
        self.current_trans = TRANSLATIONS[next_idx]

        # Query text for the new translation
        ref = self.verse_data.get("reference", "")
        all_trans = db.get_all_translations_for_ref(ref)
        if self.current_trans in all_trans:
            self.verse_data["text"] = all_trans[self.current_trans]
            self.verse_data["translation"] = self.current_trans
            self.trans_badge.setText(self.current_trans)
            self.cycle_trans_btn.setText(f" {self.current_trans}")
            self._update_scripture_html()

        # Update verse_id for new translation and sync pinned state
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM verses WHERE reference = ? AND translation = ? LIMIT 1", (ref, self.current_trans))
            row = cursor.fetchone()
            if row:
                self.verse_id = row["id"]
                self.verse_data["id"] = self.verse_id

        self.is_pinned = db.is_verse_pinned(self.verse_id) if self.verse_id else False
        self._update_pin_ui()
