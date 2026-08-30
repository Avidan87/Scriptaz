"""
Scriptaz Unified Control Panel & Welcome Setup Window
Native macOS window with real OS title bar (🔴 🟡 🟢), crisp vector SVG icons,
Non-overlapping Auto-expanding dynamic multi-line text boxes with top-header Word Counters,
generous breathing room (680x840px), Light / Dark Mode Toggle,
Tactile Cadence Steppers, 5 Flagship Themes, and an interactive Custom Focus Bar.
"""

import sys
from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFrame, QScrollArea, QListWidget, QListWidgetItem,
    QApplication, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QSize
from PySide6.QtGui import QColor, QFont, QCursor, QIcon, QTextCursor

from core.db import db
from core.models import UserSettingsModel, ScriptureTheme, BibleTranslation, CustomThemeModel
from services.autostart import is_autostart_enabled, set_autostart_enabled
from resources.styles import get_control_panel_qss, THEMES
from resources.icons import get_svg_icon
from engine.theme_architect import theme_architect


TRANSLATIONS = ["KJV", "NKJV", "ESV", "NLT"]

FLAGSHIP_THEMES = [
    ("Peace", "Peace", "feather"),
    ("Wisdom", "Wisdom", "lightbulb"),
    ("Faith", "Faith", "shield"),
    ("Grace", "Grace", "crown"),
    ("Provision", "Provision", "wrench"),
]

THEME_WATERMARKS = {
    "Peace": "e.g. Resting in God's presence, quiet stillness, letting go of anxiety...",
    "Wisdom": "e.g. Seeking godly discernment for choices, clarity of thought, counsel...",
    "Faith": "e.g. Trusting God's promises, stepping out in boldness, unwavering hope...",
    "Grace": "e.g. Resting in Christ's finished work, receiving mercy, freedom in Him...",
    "Provision": "e.g. Trusting God as my provider, grateful stewardship, daily strength..."
}

INTERVAL_STEPS = [45, 60, 90, 120]


class AutoExpandingTextEdit(QTextEdit):
    """Multi-line text editor that expands vertically as text wraps and enforces word limits."""
    words_changed = Signal(int, int)

    def __init__(self, placeholder: str = "", max_words: int = 100, min_h: int = 44, max_h: int = 90, parent=None):
        super().__init__(parent)
        self.max_words = max_words
        self.min_h = min_h
        self.max_h = max_h
        self._current_h = min_h
        self.setPlaceholderText(placeholder)
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setFixedHeight(self.min_h)
        self.textChanged.connect(self._handle_text_changed)

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self._current_h)

    def _handle_text_changed(self):
        text = self.toPlainText()
        words = text.strip().split()
        count = len(words)

        if count > self.max_words:
            truncated = " ".join(words[:self.max_words])
            self.blockSignals(True)
            self.setPlainText(truncated)
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            self.blockSignals(False)
            count = self.max_words

        # Auto-expand vertically based on document contents
        doc_height = int(self.document().size().height()) + 14
        new_height = max(self.min_h, min(self.max_h, doc_height))
        if new_height != self._current_h:
            self._current_h = new_height
            self.setFixedHeight(new_height)
            self.updateGeometry()

        self.words_changed.emit(count, self.max_words)


class CurateWorker(QThread):
    """Background worker thread to curate custom themes without freezing UI."""
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, prompt: str, translation: str):
        super().__init__()
        self.prompt = prompt
        self.translation = translation

    def run(self):
        try:
            theme_model = theme_architect.curate_custom_theme(
                user_prompt=self.prompt,
                preferred_translation=self.translation
            )
            self.finished.emit(theme_model)
        except Exception as e:
            self.failed.emit(str(e))


class PinnedArchiveDialog(QDialog):
    """Dedicated modal for viewing and managing Pinned Verses."""
    def __init__(self, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self.setWindowTitle("Scriptaz — Pinned Verses")
        self.setFixedSize(560, 500)
        self.setObjectName("ControlPanelWindow")
        self.setStyleSheet(get_control_panel_qss(self.is_dark))
        self.setWindowFlags(Qt.Window)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        icon_lbl = QLabel()
        accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
        icon_lbl.setPixmap(get_svg_icon("pin", color=accent, size=20).pixmap(20, 20))
        header_row.addWidget(icon_lbl)

        title = QLabel("Pinned Verses Archive")
        title.setObjectName("PanelHeaderTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)

        subtitle = QLabel("Your permanent treasury of daily spiritual anchors.")
        subtitle.setObjectName("PanelHeaderSubtitle")
        layout.addWidget(subtitle)

        # List
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {THEMES['dark']['bg_card'] if self.is_dark else THEMES['light']['bg_card']};
                border: 1px solid {THEMES['dark']['border'] if self.is_dark else THEMES['light']['border']};
                border-radius: 10px;
                padding: 8px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {THEMES['dark']['border_subtle'] if self.is_dark else THEMES['light']['border_subtle']};
            }}
        """)
        layout.addWidget(self.list_widget)
        self._populate_list()

        # Close
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Done")
        close_btn.setObjectName("PrimaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _populate_list(self):
        self.list_widget.clear()
        pinned = db.get_pinned_archive()
        if not pinned:
            item = QListWidgetItem("No pinned verses yet. Pin verses from the popup card!")
            self.list_widget.addItem(item)
            return

        for p in pinned:
            widget = QWidget()
            row = QHBoxLayout(widget)
            row.setContentsMargins(4, 4, 4, 4)
            
            info = QVBoxLayout()
            accent_color = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
            ref_lbl = QLabel(f"<b>{p.reference}</b> <span style='color:{accent_color};'>[{p.translation.value}]</span>")
            ref_lbl.setStyleSheet("font-size: 13px;")
            days_lbl = QLabel(f"Active Cycle: {p.days_remaining} days left" if p.days_remaining > 0 else "Archived in Memory")
            days_lbl.setStyleSheet("font-size: 11px; color: #8E95A5;")
            info.addWidget(ref_lbl)
            info.addWidget(days_lbl)
            row.addLayout(info)
            row.addStretch()

            unpin_btn = QPushButton("Unpin")
            unpin_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.06);
                    color: #A0A7B5;
                    border: 1px solid #23262F;
                    border-radius: 6px;
                    padding: 5px 12px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    color: #C59A4E;
                    border-color: #C59A4E;
                }
            """)
            unpin_btn.clicked.connect(lambda _, vid=p.verse_id: self._unpin(vid))
            row.addWidget(unpin_btn)

            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _unpin(self, verse_id: int):
        db.unpin_verse(verse_id)
        self._populate_list()


class ThemeHistoryDialog(QDialog):
    """
    Searchable Theme History & Fast Focus Switcher Dialog.
    Features:
    - Real-time search by topic, prompt, or title.
    - Default view: Shows the Last 5 Recent Themes at the top with quick selection badges.
    - Full list of all saved themes with one-click activation and generous card breathing room.
    """
    theme_selected = Signal(int, str)  # (theme_id, title)

    def __init__(self, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self.setWindowTitle("Focus History & Search")
        self.setFixedSize(620, 540)
        self.setStyleSheet(get_control_panel_qss(self.is_dark))
        self.all_themes = db.get_all_custom_themes()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)

        # Header
        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        title = QLabel("Focus History & Search")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {THEMES['dark']['text_primary'] if self.is_dark else THEMES['light']['text_primary']};")
        sub = QLabel(f"Browse, search, and switch between your {len(self.all_themes)} curated focuses.")
        sub.setStyleSheet("font-size: 12px; color: #8E95A5;")
        header_text.addWidget(title)
        header_text.addWidget(sub)
        layout.addLayout(header_text)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by keyword, topic, or title (e.g. 'Peace', 'Leadership')...")
        self.search_input.addAction(get_svg_icon("search", color="#8E95A5", size=14), QLineEdit.LeadingPosition)
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # Scrollable List Area
        self.list_widget = QListWidget()
        c = THEMES['dark'] if self.is_dark else THEMES['light']
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 10px;
                padding: 8px;
            }}
            QListWidget::item {{
                background: transparent;
                border: none;
                margin-bottom: 6px;
                padding: 0px;
            }}
        """)
        layout.addWidget(self.list_widget, 1)

        # Footer
        footer = QHBoxLayout()
        self.count_lbl = QLabel(f"{len(self.all_themes)} themes saved")
        self.count_lbl.setStyleSheet("font-size: 11px; color: #8E95A5;")
        footer.addWidget(self.count_lbl)
        footer.addStretch()

        close_btn = QPushButton("Done")
        close_btn.setObjectName("SecondaryBtn")
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        self._populate_list(query="")

    def _on_search_changed(self, text: str):
        self._populate_list(query=text.strip())

    def _populate_list(self, query: str = ""):
        self.list_widget.clear()
        query_lower = query.lower()

        if query_lower:
            matched = [
                t for t in self.all_themes
                if query_lower in t.title.lower() or
                   query_lower in (t.user_prompt or "").lower() or
                   query_lower in (t.theological_summary or "").lower()
            ]
            self.count_lbl.setText(f"Found {len(matched)} matching themes")
            if not matched:
                item = QListWidgetItem()
                no_res = QLabel(f"No saved themes found matching '{query}'.")
                no_res.setAlignment(Qt.AlignCenter)
                no_res.setStyleSheet("font-size: 12px; color: #8E95A5; padding: 30px;")
                item.setSizeHint(QSize(540, 90))
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, no_res)
                return

            for t in matched:
                self._add_theme_item(t, is_recent=False)
        else:
            self.count_lbl.setText(f"{len(self.all_themes)} themes saved")
            # Show Recent Focuses (Last 5)
            recent_5 = self.all_themes[:5]
            if recent_5:
                rec_hdr = QListWidgetItem()
                rec_hdr.setFlags(Qt.NoItemFlags)
                rec_lbl = QLabel("  RECENT FOCUSES (LAST 5)")
                accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
                rec_lbl.setStyleSheet(f"font-size: 10.5px; font-weight: 700; color: {accent}; letter-spacing: 0.8px; padding: 6px 4px 4px 4px;")
                rec_hdr.setSizeHint(QSize(540, 32))
                self.list_widget.addItem(rec_hdr)
                self.list_widget.setItemWidget(rec_hdr, rec_lbl)

                for t in recent_5:
                    self._add_theme_item(t, is_recent=True)

            # Show Older Saved Focuses
            other_themes = self.all_themes[5:]
            if other_themes:
                all_hdr = QListWidgetItem()
                all_hdr.setFlags(Qt.NoItemFlags)
                all_lbl = QLabel("  OLDER SAVED FOCUSES")
                all_lbl.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #8E95A5; letter-spacing: 0.8px; padding: 12px 4px 4px 4px;")
                all_hdr.setSizeHint(QSize(540, 36))
                self.list_widget.addItem(all_hdr)
                self.list_widget.setItemWidget(all_hdr, all_lbl)

                for t in other_themes:
                    self._add_theme_item(t, is_recent=False)

    def _add_theme_item(self, theme: CustomThemeModel, is_recent: bool = False):
        item = QListWidgetItem()
        c = THEMES['dark'] if self.is_dark else THEMES['light']
        accent = c['accent']

        widget = QFrame()
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_secondary']};
                border: 1px solid {c['border']};
                border-radius: 9px;
            }}
            QFrame:hover {{
                border-color: {accent};
                background-color: {c['bg_subtle']};
            }}
        """)
        row = QHBoxLayout(widget)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_icon("feather", color=accent, size=16).pixmap(16, 16))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        row.addWidget(icon_lbl)

        # Text block
        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        
        title_row = QHBoxLayout()
        title_lbl = QLabel(theme.title)
        title_lbl.setStyleSheet(f"font-size: 13.5px; font-weight: 600; color: {c['text_primary']}; background: transparent; border: none;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        text_box.addLayout(title_row)

        sub_text = theme.user_prompt or theme.theological_summary or "Curated spiritual focus"
        if len(sub_text) > 80:
            sub_text = sub_text[:77] + "..."
        prompt_lbl = QLabel(sub_text)
        prompt_lbl.setStyleSheet("font-size: 11.5px; color: #8E95A5; background: transparent; border: none;")
        text_box.addWidget(prompt_lbl)
        row.addLayout(text_box, 1)

        # Select Action Button
        sel_btn = QPushButton("Select")
        sel_btn.setObjectName("SecondaryBtn")
        sel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        sel_btn.setStyleSheet("padding: 6px 16px; font-size: 12px; font-weight: 600;")
        sel_btn.clicked.connect(lambda _, tid=theme.id, ttitle=theme.title: self._select_and_close(tid, ttitle))
        row.addWidget(sel_btn)

        item.setSizeHint(QSize(540, 68))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _select_and_close(self, theme_id: int, title: str):
        self.theme_selected.emit(theme_id, title)
        self.accept()


class HowItWorksDialog(QDialog):
    """
    Intelligent Welcome & Architectural Guide for Scriptaz.
    Explains the vision, workflow, and core pillars of Scriptaz with modern visual cards.
    Fully adaptive to Light and Dark modes.
    """
    def __init__(self, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self.setWindowTitle("About Scriptaz — How It Works")
        self.setFixedSize(620, 640)
        self.setObjectName("ControlPanelWindow")
        self.setWindowFlags(Qt.Window)
        self.setStyleSheet(get_control_panel_qss(self.is_dark))
        self._init_ui()

    def _init_ui(self):
        c = THEMES["dark"] if self.is_dark else THEMES["light"]
        accent = c["accent"]
        card_bg = c["bg_card"] if not self.is_dark else c["bg_secondary"]
        subtext_color = c["text_secondary"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        # 1. Hero Header
        hero_layout = QHBoxLayout()
        hero_layout.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_icon("feather", color=accent, size=28).pixmap(28, 28))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        hero_layout.addWidget(icon_lbl, alignment=Qt.AlignTop)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)
        title = QLabel("Welcome to Scriptaz")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {c['text_primary']}; background: transparent;")
        subtitle = QLabel("God's Living Word for Your Active Workday")
        subtitle.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {accent}; background: transparent;")
        intro = QLabel(
            "Scriptaz is a mindful desktop companion crafted to anchor your thoughts in biblical truth "
            "throughout your workday. It synchronizes with your natural workflow—never interrupting abruptly, "
            "always timely and enriching."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"font-size: 12px; color: {subtext_color}; line-height: 1.4; background: transparent;")

        hero_text.addWidget(title)
        hero_text.addWidget(subtitle)
        hero_text.addWidget(intro)
        hero_layout.addLayout(hero_text, 1)
        layout.addLayout(hero_layout)

        # 2. Four Pillars Cards Container
        cards_layout = QVBoxLayout()
        cards_layout.setSpacing(10)

        pillars = [
            (
                "feather",
                "Curated Spiritual Focus",
                "Anchor in 5 foundational themes (Peace, Wisdom, Faith, Grace, Provision) or explore custom AI-curated theological topics tailored to your exact projects and challenges."
            ),
            (
                "clock",
                "Active-Time Smart Scheduling",
                "Scriptaz only accumulates time when you are actively typing or using your mouse. If you step away for a break, meeting, or lunch, timer tracking pauses automatically."
            ),
            (
                "lightbulb",
                "Deep Insight Wings & Context",
                "Every scripture drop includes surrounding chapter context, original Greek and Hebrew root insights, and actionable reflections for practical workday application."
            ),
            (
                "pin",
                "7-Day Active Memory Pinning",
                "Pin verses that speak directly to your heart into your active 7-day memory rotation. Repetition turns fleeting inspiration into deep, lasting spiritual conviction."
            ),
        ]

        for icon_name, heading, desc in pillars:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {card_bg};
                    border: 1px solid {c['border']};
                    border-radius: 10px;
                }}
            """)
            card_row = QHBoxLayout(card)
            card_row.setContentsMargins(14, 10, 14, 10)
            card_row.setSpacing(12)

            p_icon = QLabel()
            p_icon.setPixmap(get_svg_icon(icon_name, color=accent, size=18).pixmap(18, 18))
            p_icon.setStyleSheet("background: transparent; border: none;")
            card_row.addWidget(p_icon, alignment=Qt.AlignTop)

            p_text = QVBoxLayout()
            p_text.setSpacing(2)
            p_head = QLabel(heading)
            p_head.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {c['text_primary']}; background: transparent; border: none;")
            p_desc = QLabel(desc)
            p_desc.setWordWrap(True)
            p_desc.setStyleSheet(f"font-size: 11.5px; color: {subtext_color}; line-height: 1.35; background: transparent; border: none;")
            p_text.addWidget(p_head)
            p_text.addWidget(p_desc)
            card_row.addLayout(p_text, 1)

            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        # 3. Footer with Dismiss CTA
        footer = QHBoxLayout()
        privacy_lbl = QLabel("🛡️ 100% Offline-First, Private & Secure")
        privacy_lbl.setStyleSheet(f"font-size: 11px; color: {c['text_muted']}; background: transparent;")
        footer.addWidget(privacy_lbl)
        footer.addStretch()

        got_it_btn = QPushButton("Got It, Let's Begin →")
        got_it_btn.setObjectName("PrimaryBtn")
        got_it_btn.setCursor(QCursor(Qt.PointingHandCursor))
        got_it_btn.clicked.connect(self.accept)
        footer.addWidget(got_it_btn)

        layout.addLayout(footer)


class SettingsDialog(QDialog):
    """Modernized Scriptaz Control Panel & Welcome Setup Window."""

    settings_saved = Signal(UserSettingsModel)

    def __init__(self, is_welcome_mode: bool = False, parent=None):
        super().__init__(parent)
        self.is_welcome_mode = is_welcome_mode
        self.settings = db.get_settings()
        self.is_dark = self.settings.dark_mode
        
        # Working state
        if self.is_welcome_mode:
            self.selected_translation = "NKJV"
            self.selected_theme = "Peace"
            self.active_custom_id = None
            self.active_custom_title = None
            self.interval_minutes = 60
            self.daily_limit = 5
        else:
            self.selected_translation = self.settings.active_translation.value
            self.selected_theme = self.settings.active_theme.value
            self.active_custom_id = self.settings.active_custom_theme_id
            self.active_custom_title = self.settings.active_custom_theme_title
            self.interval_minutes = self.settings.interval_minutes if self.settings.interval_minutes in INTERVAL_STEPS else 60
            self.daily_limit = max(1, min(10, self.settings.daily_limit))

        self.setWindowTitle("Scriptaz")
        self.setFixedSize(680, 785)
        self.setObjectName("ControlPanelWindow")
        self.setWindowFlags(Qt.Window)

        # Baseline state for dirty-tracking (Save button is disabled until something changes)
        if not self.is_welcome_mode:
            self._initial_state = {
                "name": (self.settings.user_name or "").strip(),
                "translation": self.settings.active_translation.value,
                "theme": self.settings.active_theme.value,
                "custom_id": self.settings.active_custom_theme_id,
                "context": "",
                "interval": self.interval_minutes,
                "limit": self.daily_limit,
                "dark_mode": self.is_dark
            }

        self._apply_theme()
        self._init_ui()

    def _apply_theme(self):
        self.setStyleSheet(get_control_panel_qss(self.is_dark))

    def _init_ui(self):
        if self.layout():
            self.save_btn = None
            QWidget().setLayout(self.layout())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(20)

        # -------------------------------------------------------------
        # 1. Header Row (Title & Light/Dark Appearance Switcher)
        # -------------------------------------------------------------
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        title = QLabel("Welcome to Scriptaz" if self.is_welcome_mode else "Scriptaz Control Panel")
        title.setObjectName("PanelHeaderTitle")
        subtitle = QLabel("Set your spiritual rhythm for the active workday.")
        subtitle.setObjectName("PanelHeaderSubtitle")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)

        header.addStretch()

        # Action Buttons on Right (Info + Theme Toggle)
        header_actions = QHBoxLayout()
        header_actions.setSpacing(8)

        self.info_btn = QPushButton()
        self.info_btn.setObjectName("SecondaryBtn")
        self.info_btn.setToolTip("How Scriptaz Works")
        self.info_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.info_btn.setFixedSize(32, 32)
        accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
        self.info_btn.setIcon(get_svg_icon("info", color=accent, size=15))
        self.info_btn.setIconSize(QSize(15, 15))
        self.info_btn.clicked.connect(self._open_how_it_works)
        header_actions.addWidget(self.info_btn)

        # Compact Icon-Only 2-Segment Light / Dark Capsule Toggle
        self.theme_capsule = QFrame()
        self.theme_capsule.setObjectName("ThemeToggleCapsule")
        self.theme_capsule.setFixedSize(66, 32)
        caps_layout = QHBoxLayout(self.theme_capsule)
        caps_layout.setContentsMargins(3, 3, 3, 3)
        caps_layout.setSpacing(2)

        self.light_seg_btn = QPushButton()
        self.light_seg_btn.setToolTip("Light Mode")
        self.light_seg_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.light_seg_btn.setFixedSize(28, 24)
        self.light_seg_btn.setIcon(get_svg_icon("sun", color=THEMES['light']['accent'] if not self.is_dark else "#8E95A5", size=14))
        self.light_seg_btn.setIconSize(QSize(14, 14))
        self.light_seg_btn.setObjectName("ThemeSegActive" if not self.is_dark else "ThemeSegInactive")
        self.light_seg_btn.clicked.connect(lambda: self._set_dark_mode(False))

        self.dark_seg_btn = QPushButton()
        self.dark_seg_btn.setToolTip("Dark Mode")
        self.dark_seg_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.dark_seg_btn.setFixedSize(28, 24)
        self.dark_seg_btn.setIcon(get_svg_icon("moon", color=THEMES['dark']['accent'] if self.is_dark else "#8E95A5", size=14))
        self.dark_seg_btn.setIconSize(QSize(14, 14))
        self.dark_seg_btn.setObjectName("ThemeSegActive" if self.is_dark else "ThemeSegInactive")
        self.dark_seg_btn.clicked.connect(lambda: self._set_dark_mode(True))

        caps_layout.addWidget(self.light_seg_btn)
        caps_layout.addWidget(self.dark_seg_btn)
        header_actions.addWidget(self.theme_capsule)

        header.addLayout(header_actions)

        main_layout.addLayout(header)

        # -------------------------------------------------------------
        # 2. Section 1: User Name
        # -------------------------------------------------------------
        name_section = QVBoxLayout()
        name_section.setSpacing(6)
        name_lbl = QLabel("YOUR NAME")
        name_lbl.setObjectName("SectionTitle")
        self.name_input = QLineEdit(self.settings.user_name)
        self.name_input.setPlaceholderText("Enter your name...")
        name_section.addWidget(name_lbl)
        name_section.addWidget(self.name_input)
        main_layout.addLayout(name_section)

        # -------------------------------------------------------------
        # 3. Section 2: 4-Segment Bible Translation Bar
        # -------------------------------------------------------------
        trans_section = QVBoxLayout()
        trans_section.setSpacing(6)
        trans_lbl = QLabel("BIBLE TRANSLATION")
        trans_lbl.setObjectName("SectionTitle")
        trans_section.addWidget(trans_lbl)

        self.trans_buttons: Dict[str, QPushButton] = {}
        trans_bar = QHBoxLayout()
        trans_bar.setSpacing(8)
        for t in TRANSLATIONS:
            btn = QPushButton(t)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            if t == self.selected_translation:
                btn.setObjectName("TransSegmentSelected")
            else:
                btn.setObjectName("TransSegment")
            btn.clicked.connect(lambda _, trans=t: self._select_translation(trans))
            self.trans_buttons[t] = btn
            trans_bar.addWidget(btn, 1)
        trans_section.addLayout(trans_bar)
        main_layout.addLayout(trans_section)

        # -------------------------------------------------------------
        # 4. Section 3: 5 Flagship Preset Themes with Auto-Expanding Reason Box
        # -------------------------------------------------------------
        theme_section = QVBoxLayout()
        theme_section.setSpacing(7)
        theme_lbl = QLabel("PRESET THEMES")
        theme_lbl.setObjectName("SectionTitle")
        theme_section.addWidget(theme_lbl)

        self.theme_pills: Dict[str, QPushButton] = {}
        theme_grid = QHBoxLayout()
        theme_grid.setSpacing(8)
        for code, label, icon_name in FLAGSHIP_THEMES:
            btn = QPushButton(f" {label}")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            is_sel = (self.selected_theme == code)
            icon_color = THEMES["dark"]["accent"] if (is_sel and self.is_dark) else (THEMES["light"]["accent"] if is_sel else "#8E95A5")
            btn.setIcon(get_svg_icon(icon_name, color=icon_color, size=15))
            btn.setIconSize(QSize(15, 15))
            btn.setObjectName("ThemePillSelected" if is_sel else "ThemePill")
            btn.clicked.connect(lambda _, th=code: self._select_preset_theme(th))
            self.theme_pills[code] = btn
            theme_grid.addWidget(btn, 1)
        theme_section.addLayout(theme_grid)

        # Clean Context / Personal Reason Container (No enclosing border)
        self.context_container = QWidget()
        ctx_layout = QVBoxLayout(self.context_container)
        ctx_layout.setContentsMargins(0, 8, 0, 0)
        ctx_layout.setSpacing(6)

        ctx_header = QHBoxLayout()
        self.context_prompt_lbl = QLabel(f"Why {self.selected_theme} today? (Optional)")
        self.context_prompt_lbl.setStyleSheet("font-size: 11.5px; color: #8E95A5; font-weight: 600;")
        self.context_counter_lbl = QLabel("0 / 50 words")
        self.context_counter_lbl.setStyleSheet("font-size: 11px; color: #687082;")
        ctx_header.addWidget(self.context_prompt_lbl)
        ctx_header.addStretch()
        ctx_header.addWidget(self.context_counter_lbl)
        ctx_layout.addLayout(ctx_header)

        self.context_input = AutoExpandingTextEdit(
            placeholder=THEME_WATERMARKS.get(self.selected_theme, "e.g. Resting in God's presence, quiet stillness, letting go of anxiety..."),
            max_words=50,
            min_h=42,
            max_h=80
        )
        self.context_input.words_changed.connect(self._on_context_words_changed)
        self._update_context_counter(0, 50)

        ctx_layout.addWidget(self.context_input)
        theme_section.addWidget(self.context_container)

        # Hide preset context container if currently on Custom theme
        if self.selected_theme == "Custom":
            self.context_container.hide()

        main_layout.addLayout(theme_section)

        # -------------------------------------------------------------
        # 5. Section 4: Dedicated Custom Focus Card (Non-Overlapping Layout)
        # -------------------------------------------------------------
        ai_section = QVBoxLayout()
        ai_section.setSpacing(7)
        ai_lbl = QLabel("CUSTOM FOCUS")
        ai_lbl.setObjectName("SectionTitle")
        ai_section.addWidget(ai_lbl)

        self.custom_card = QFrame()
        self.custom_card.setObjectName("AIExploreCard")
        self.custom_card_layout = QVBoxLayout(self.custom_card)
        self.custom_card_layout.setContentsMargins(14, 12, 14, 12)
        self.custom_card_layout.setSpacing(8)

        # --- State A: Input / Curate Container ---
        self.custom_input_container = QWidget()
        input_container_layout = QVBoxLayout(self.custom_input_container)
        input_container_layout.setContentsMargins(0, 0, 0, 0)
        input_container_layout.setSpacing(6)

        # Top Header: Title on Left, Word Counter on Right
        custom_header_row = QHBoxLayout()
        custom_input_prompt_lbl = QLabel("What would you like to explore today?")
        custom_input_prompt_lbl.setStyleSheet("font-size: 11.5px; color: #8E95A5; font-weight: 600;")
        self.custom_counter_lbl = QLabel("0 / 100 words")
        self.custom_counter_lbl.setStyleSheet("font-size: 11px; color: #687082;")
        custom_header_row.addWidget(custom_input_prompt_lbl)
        custom_header_row.addStretch()
        custom_header_row.addWidget(self.custom_counter_lbl)
        input_container_layout.addLayout(custom_header_row)

        # Side-by-side Prompt Row: Text Input + Curate Button
        prompt_bar = QHBoxLayout()
        prompt_bar.setSpacing(8)

        self.custom_prompt_input = AutoExpandingTextEdit(
            placeholder="Enter any topic, passage, or season (e.g. 'Gratitude', 'Parenting')...",
            max_words=100,
            min_h=42,
            max_h=75
        )
        self.custom_prompt_input.words_changed.connect(self._on_custom_words_changed)
        prompt_bar.addWidget(self.custom_prompt_input, 1)

        self.curate_btn = QPushButton(" Curate")
        self.curate_btn.setObjectName("CurateBtn")
        self.curate_btn.setIcon(get_svg_icon("sparkles", color="#0D0E11", size=14))
        self.curate_btn.setIconSize(QSize(14, 14))
        self.curate_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.curate_btn.setFixedHeight(42)
        self.curate_btn.setMinimumWidth(95)
        self.curate_btn.clicked.connect(self._on_curate_clicked)
        prompt_bar.addWidget(self.curate_btn)

        input_container_layout.addLayout(prompt_bar)
        self.custom_card_layout.addWidget(self.custom_input_container)

        # --- State B: Active Theme Banner Container ---
        self.custom_active_container = QWidget()
        active_row = QHBoxLayout(self.custom_active_container)
        active_row.setContentsMargins(4, 2, 4, 2)
        active_row.setSpacing(12)

        self.active_theme_label = QLabel()
        self.active_theme_label.setStyleSheet(f"""
            font-size: 13px; font-weight: 700;
            color: {THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']};
        """)
        active_row.addWidget(self.active_theme_label, 1)

        self.change_focus_btn = QPushButton("Change Focus")
        self.change_focus_btn.setObjectName("SecondaryBtn")
        self.change_focus_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.change_focus_btn.clicked.connect(self._show_custom_input)
        active_row.addWidget(self.change_focus_btn)
        self.custom_card_layout.addWidget(self.custom_active_container)

        # Status Label
        self.curate_status_lbl = QLabel()
        self.curate_status_lbl.setStyleSheet(f"font-size: 11.5px; color: {THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']}; font-weight: 600;")
        # Searchable Focus History Button (ONLY in settings mode for existing users)
        if not self.is_welcome_mode:
            saved_themes = db.get_all_custom_themes()
            if saved_themes:
                history_row = QHBoxLayout()
                history_row.setContentsMargins(0, 4, 0, 0)
                history_row.setSpacing(8)

                hist_lbl = QLabel("History:")
                hist_lbl.setStyleSheet("font-size: 11.5px; color: #8E95A5; font-weight: 600;")
                history_row.addWidget(hist_lbl)

                self.history_btn = QPushButton(f" Search & Switch Past Focus ({len(saved_themes)} saved)...")
                self.history_btn.setObjectName("SecondaryBtn")
                accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
                self.history_btn.setIcon(get_svg_icon("search", color=accent, size=13))
                self.history_btn.setIconSize(QSize(13, 13))
                self.history_btn.setCursor(QCursor(Qt.PointingHandCursor))
                self.history_btn.setStyleSheet("text-align: left; padding: 7px 12px;")
                self.history_btn.clicked.connect(self._open_theme_history_dialog)
                history_row.addWidget(self.history_btn, 1)

                self.custom_card_layout.addLayout(history_row)

        ai_section.addWidget(self.custom_card)
        main_layout.addLayout(ai_section)

        # Initialize visual custom focus state
        if self.selected_theme == "Custom" and self.active_custom_title:
            self._show_active_custom_banner(self.active_custom_title)
        else:
            self._show_custom_input()

        # -------------------------------------------------------------
        # 6. Section 5: Workday Cadence (Tactile Steppers)
        # -------------------------------------------------------------
        cadence_section = QVBoxLayout()
        cadence_section.setSpacing(6)
        cadence_lbl = QLabel("WORKDAY CADENCE")
        cadence_lbl.setObjectName("SectionTitle")
        cadence_section.addWidget(cadence_lbl)

        steppers_row = QHBoxLayout()
        steppers_row.setSpacing(18)

        # Interval Stepper
        int_box = QVBoxLayout()
        int_box.setSpacing(4)
        int_title = QLabel("Interval Timer")
        int_title.setStyleSheet("font-size: 11.5px; color: #8E95A5;")
        
        int_capsule = QFrame()
        int_capsule.setObjectName("StepperCapsule")
        int_caps_layout = QHBoxLayout(int_capsule)
        int_caps_layout.setContentsMargins(4, 4, 4, 4)
        int_caps_layout.setSpacing(6)

        self.int_minus_btn = QPushButton("−")
        self.int_minus_btn.setObjectName("StepperBtn")
        self.int_minus_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.int_minus_btn.clicked.connect(self._dec_interval)

        self.int_display = QLabel(self._format_interval(self.interval_minutes))
        self.int_display.setObjectName("StepperDisplay")

        self.int_plus_btn = QPushButton("+")
        self.int_plus_btn.setObjectName("StepperBtn")
        self.int_plus_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.int_plus_btn.clicked.connect(self._inc_interval)

        int_caps_layout.addWidget(self.int_minus_btn)
        int_caps_layout.addWidget(self.int_display, 1)
        int_caps_layout.addWidget(self.int_plus_btn)
        int_box.addWidget(int_title)
        int_box.addWidget(int_capsule)
        steppers_row.addLayout(int_box, 1)

        # Daily Limit Stepper
        lim_box = QVBoxLayout()
        lim_box.setSpacing(4)
        lim_title = QLabel("Daily Limit")
        lim_title.setStyleSheet("font-size: 11.5px; color: #8E95A5;")

        lim_capsule = QFrame()
        lim_capsule.setObjectName("StepperCapsule")
        lim_caps_layout = QHBoxLayout(lim_capsule)
        lim_caps_layout.setContentsMargins(4, 4, 4, 4)
        lim_caps_layout.setSpacing(6)

        self.lim_minus_btn = QPushButton("−")
        self.lim_minus_btn.setObjectName("StepperBtn")
        self.lim_minus_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.lim_minus_btn.clicked.connect(self._dec_limit)

        self.lim_display = QLabel(f"{self.daily_limit} verses")
        self.lim_display.setObjectName("StepperDisplay")

        self.lim_plus_btn = QPushButton("+")
        self.lim_plus_btn.setObjectName("StepperBtn")
        self.lim_plus_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.lim_plus_btn.clicked.connect(self._inc_limit)

        lim_caps_layout.addWidget(self.lim_minus_btn)
        lim_caps_layout.addWidget(self.lim_display, 1)
        lim_caps_layout.addWidget(self.lim_plus_btn)
        lim_box.addWidget(lim_title)
        lim_box.addWidget(lim_capsule)
        steppers_row.addLayout(lim_box, 1)
        cadence_section.addLayout(steppers_row)
        main_layout.addLayout(cadence_section)

        # -------------------------------------------------------------
        # 7. Footer: Action Buttons
        # -------------------------------------------------------------
        main_layout.addSpacing(6)
        footer_row = QHBoxLayout()
        footer_row.setSpacing(14)

        # Pinned Archive Modal Button (ONLY in Settings Mode, NOT in Welcome onboarding)
        if not self.is_welcome_mode:
            pinned_count = len(db.get_pinned_archive())
            self.pinned_btn = QPushButton(f" Pinned Archive ({pinned_count})")
            self.pinned_btn.setObjectName("SecondaryBtn")
            accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
            self.pinned_btn.setIcon(get_svg_icon("pin", color=accent, size=15))
            self.pinned_btn.setIconSize(QSize(15, 15))
            self.pinned_btn.setCursor(QCursor(Qt.PointingHandCursor))
            self.pinned_btn.clicked.connect(self._open_pinned_archive)
            footer_row.addWidget(self.pinned_btn)

        footer_row.addStretch()

        # Primary Save / Begin Button
        cta_text = "Begin My Workday →" if self.is_welcome_mode else "Save Preferences →"
        self.save_btn = QPushButton(cta_text)
        self.save_btn.setObjectName("PrimaryBtn")
        self.save_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.save_btn.clicked.connect(self._save_and_close)
        footer_row.addWidget(self.save_btn)

        # Wire up dirty-checking signals
        self.name_input.textChanged.connect(self._check_dirty)
        self.context_input.textChanged.connect(self._check_dirty)

        main_layout.addLayout(footer_row)
        self._update_stepper_ui()

    def _check_dirty(self):
        if self.is_welcome_mode or not hasattr(self, "_initial_state") or not getattr(self, "save_btn", None):
            return
        try:
            current_name = self.name_input.text().strip() if hasattr(self, "name_input") else ""
            current_context = self.context_input.toPlainText().strip() if hasattr(self, "context_input") else ""
            
            is_dirty = (
                current_name != self._initial_state["name"] or
                self.selected_translation != self._initial_state["translation"] or
                self.selected_theme != self._initial_state["theme"] or
                self.active_custom_id != self._initial_state["custom_id"] or
                current_context != self._initial_state["context"] or
                self.interval_minutes != self._initial_state["interval"] or
                self.daily_limit != self._initial_state["limit"] or
                self.is_dark != self._initial_state["dark_mode"]
            )
            self.save_btn.setEnabled(is_dirty)
        except (RuntimeError, AttributeError):
            pass

    def _on_context_words_changed(self, count: int, max_w: int):
        self._update_context_counter(count, max_w)

    def _update_context_counter(self, count: int, max_w: int):
        accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
        color = accent if count >= max_w * 0.9 else "#687082"
        self.context_counter_lbl.setText(f"{count} / {max_w} words")
        self.context_counter_lbl.setStyleSheet(f"font-size: 11px; color: {color};")

    def _on_custom_words_changed(self, count: int, max_w: int):
        accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
        color = accent if count >= max_w * 0.9 else "#687082"
        self.custom_counter_lbl.setText(f"{count} / {max_w} words")
        self.custom_counter_lbl.setStyleSheet(f"font-size: 11px; color: {color};")

    def _set_dark_mode(self, is_dark: bool):
        if self.is_dark == is_dark:
            return
        self.is_dark = is_dark
        self._apply_theme()
        self._init_ui()
        self._check_dirty()

    def _format_interval(self, minutes: int) -> str:
        if minutes == 45:
            return "45 mins"
        elif minutes == 60:
            return "1 hr"
        elif minutes == 90:
            return "1 hr 30 mins"
        elif minutes == 120:
            return "2 hrs"
        return f"{minutes} mins"

    def _update_stepper_ui(self):
        self.int_display.setText(self._format_interval(self.interval_minutes))
        idx = INTERVAL_STEPS.index(self.interval_minutes) if self.interval_minutes in INTERVAL_STEPS else 1
        self.int_minus_btn.setEnabled(idx > 0)
        self.int_plus_btn.setEnabled(idx < len(INTERVAL_STEPS) - 1)

        self.lim_display.setText(f"{self.daily_limit} verse" if self.daily_limit == 1 else f"{self.daily_limit} verses")
        self.lim_minus_btn.setEnabled(self.daily_limit > 1)
        self.lim_plus_btn.setEnabled(self.daily_limit < 10)
        self._check_dirty()

    def _dec_interval(self):
        if self.interval_minutes in INTERVAL_STEPS:
            idx = INTERVAL_STEPS.index(self.interval_minutes)
            if idx > 0:
                self.interval_minutes = INTERVAL_STEPS[idx - 1]
                self._update_stepper_ui()

    def _inc_interval(self):
        if self.interval_minutes in INTERVAL_STEPS:
            idx = INTERVAL_STEPS.index(self.interval_minutes)
            if idx < len(INTERVAL_STEPS) - 1:
                self.interval_minutes = INTERVAL_STEPS[idx + 1]
                self._update_stepper_ui()

    def _dec_limit(self):
        if self.daily_limit > 1:
            self.daily_limit -= 1
            self._update_stepper_ui()

    def _inc_limit(self):
        if self.daily_limit < 10:
            self.daily_limit += 1
            self._update_stepper_ui()

    def _select_translation(self, trans: str):
        self.selected_translation = trans
        for t, btn in self.trans_buttons.items():
            btn.setObjectName("TransSegmentSelected" if t == trans else "TransSegment")
            btn.setStyle(btn.style())
        self._check_dirty()

    def _select_preset_theme(self, theme_code: str):
        self.selected_theme = theme_code
        self.active_custom_id = None
        self.active_custom_title = None

        for code, btn in self.theme_pills.items():
            is_sel = (code == theme_code)
            btn.setObjectName("ThemePillSelected" if is_sel else "ThemePill")
            icon_name = dict((c, ic) for c, l, ic in FLAGSHIP_THEMES).get(code, "feather")
            accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
            btn.setIcon(get_svg_icon(icon_name, color=accent if is_sel else "#8E95A5", size=15))
            btn.setStyle(btn.style())

        self.context_prompt_lbl.setText(f"Why {theme_code} today? (Optional)")
        self.context_input.setPlaceholderText(THEME_WATERMARKS.get(theme_code, "e.g. Resting in God's presence, quiet stillness, letting go of anxiety..."))
        self.context_input.clear()
        self.context_container.show()

        self._show_custom_input()
        self.curate_status_lbl.hide()
        self._check_dirty()

    def _show_custom_input(self):
        self.custom_active_container.hide()
        self.curate_status_lbl.hide()
        self.custom_input_container.show()
        self.custom_prompt_input.clear()
        self.custom_prompt_input.setFocus()
        border_col = THEMES['dark']['border'] if self.is_dark else THEMES['light']['border']
        self.custom_card.setStyleSheet(f"""
            QFrame#AIExploreCard {{
                background: {THEMES['dark']['bg_secondary'] if self.is_dark else THEMES['light']['bg_secondary']};
                border: 1px solid {border_col};
                border-radius: 12px;
            }}
        """)

    def _show_active_custom_banner(self, title: str):
        self.custom_input_container.hide()
        self.curate_status_lbl.hide()
        accent = THEMES['dark']['accent'] if self.is_dark else THEMES['light']['accent']
        text_color = THEMES['dark']['text_primary'] if self.is_dark else THEMES['light']['text_primary']
        self.active_theme_label.setText(
            f"<span style='color:{text_color}; font-size:12px; font-weight:500;'>Active Focus:</span> "
            f"<span style='color:{accent}; font-size:13.5px; font-weight:700;'>\"{title}\"</span>"
        )
        self.custom_active_container.show()
        self.custom_card.setStyleSheet(f"""
            QFrame#AIExploreCard {{
                background: {THEMES['dark']['chip_active_bg'] if self.is_dark else THEMES['light']['chip_active_bg']};
                border: 1.5px solid {accent};
                border-radius: 12px;
            }}
        """)

    def _on_curate_clicked(self):
        prompt = self.custom_prompt_input.toPlainText().strip()
        if not prompt:
            self.custom_prompt_input.setFocus()
            return

        self.curate_btn.setEnabled(False)
        self.curate_btn.setText("Curating...")
        self.curate_status_lbl.setText("Connecting to Bible vector stream...")
        self.curate_status_lbl.show()

        self.worker = CurateWorker(prompt, self.selected_translation)
        self.worker.finished.connect(self._on_curate_success)
        self.worker.failed.connect(self._on_curate_failed)
        self.worker.start()

    def _on_curate_success(self, theme_model: CustomThemeModel):
        self.curate_btn.setEnabled(True)
        self.curate_btn.setText(" Curate")
        self.selected_theme = "Custom"
        self.active_custom_id = theme_model.id
        self.active_custom_title = theme_model.title

        # Deselect all 5 Preset Buttons
        for code, btn in self.theme_pills.items():
            btn.setObjectName("ThemePill")
            icon_name = dict((c, ic) for c, l, ic in FLAGSHIP_THEMES).get(code, "feather")
            btn.setIcon(get_svg_icon(icon_name, color="#8E95A5", size=15))
            btn.setStyle(btn.style())

        # Hide preset reason card
        self.context_container.hide()
        self.curate_status_lbl.hide()

        # Transform Custom Focus container into Active Focus Card
        self._show_active_custom_banner(theme_model.title)
        saved_themes = db.get_all_custom_themes()
        if hasattr(self, "history_btn"):
            self.history_btn.setText(f" Search & Switch Past Focus ({len(saved_themes)} saved)...")

    def _on_curate_failed(self, err_msg: str):
        self.curate_btn.setEnabled(True)
        self.curate_btn.setText(" Curate")
        self.curate_status_lbl.setText(f"Note: Saved with local anchors")

    def _open_theme_history_dialog(self):
        dlg = ThemeHistoryDialog(is_dark=self.is_dark, parent=self)
        dlg.theme_selected.connect(lambda tid, title: self._activate_saved_custom(tid, title))
        dlg.exec()
        saved_themes = db.get_all_custom_themes()
        if hasattr(self, "history_btn"):
            self.history_btn.setText(f" Search & Switch Past Focus ({len(saved_themes)} saved)...")

    def _activate_saved_custom(self, theme_id: int, title: str):
        db.activate_custom_theme(theme_id)
        self.selected_theme = "Custom"
        self.active_custom_id = theme_id
        self.active_custom_title = title

        # Deselect all preset pills
        for code, btn in self.theme_pills.items():
            btn.setObjectName("ThemePill")
            icon_name = dict((c, ic) for c, l, ic in FLAGSHIP_THEMES).get(code, "feather")
            btn.setIcon(get_svg_icon(icon_name, color="#8E95A5", size=15))
            btn.setStyle(btn.style())

        self.context_container.hide()
        self.curate_status_lbl.hide()
        self._show_active_custom_banner(title)
        self._check_dirty()

    def _open_pinned_archive(self):
        dlg = PinnedArchiveDialog(is_dark=self.is_dark, parent=self)
        dlg.exec()
        pinned_count = len(db.get_pinned_archive())
        self.pinned_btn.setText(f" Pinned Archive ({pinned_count})")

    def _open_how_it_works(self):
        dlg = HowItWorksDialog(is_dark=self.is_dark, parent=self)
        dlg.exec()

    def _save_and_close(self):
        theme_enum = ScriptureTheme.CUSTOM if self.selected_theme == "Custom" else ScriptureTheme(self.selected_theme)
        updated = UserSettingsModel(
            user_name=self.name_input.text().strip() or "Friend",
            interval_minutes=self.interval_minutes,
            daily_limit=self.daily_limit,
            active_translation=BibleTranslation(self.selected_translation),
            active_theme=theme_enum,
            active_custom_theme_id=self.active_custom_id,
            active_custom_theme_title=self.active_custom_title,
            personal_context=self.context_input.toPlainText().strip(),
            launch_on_startup=self.settings.launch_on_startup,
            dark_mode=self.is_dark,
            has_completed_onboarding=True
        )
        db.save_user_settings(updated)
        self.settings_saved.emit(updated)
        self.accept()


# Aliases for backward compatibility
PinnedVersesDialog = PinnedArchiveDialog
