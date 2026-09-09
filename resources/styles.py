"""
Scriptaz Native Stylesheet & Design System Engine
Provides Light Mode (Default) and Dark Mode stylesheets with Deep Burgundy Wine accents (#8B1A2B),
Inter typography, and clean minimalist design for macOS and Windows desktop interfaces.

Design System consulted: UI Designer (ui-ux-pro-max)
Style: Minimalism & Swiss Style — clean, spacious, functional, high contrast
Typography: Inter — clean, premium, developer-grade readability
Color Philosophy: 60-30-10 rule — muted burgundy accent, never screaming
"""

from typing import Dict
from resources.icons import get_icon_path

# ─────────────────────────────────────────────────────────
# DESIGN TOKENS (UI Designer: Minimalism + Spiritual Calm)
# ─────────────────────────────────────────────────────────
THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "bg_canvas": "#F9FAFB",
        "bg_card": "#FFFFFF",
        "bg_secondary": "#F3F4F6",
        "bg_subtle": "#E5E7EB",
        "text_primary": "#111827",        # Deep rich carbon ink (WCAG AAA contrast)
        "text_secondary": "#4B5563",      # Refined slate subtext
        "text_muted": "#6B7280",          # Accessible subtext
        "accent": "#B37B24",              # Warm Antique Ochre Gold
        "accent_hover": "#94631A",
        "accent_subtle": "rgba(179, 123, 36, 0.10)",
        "border": "#E5E7EB",
        "border_subtle": "#F3F4F6",
        "border_active": "#B37B24",
        "gold": "#B37B24",
        "btn_text": "#FFFFFF",
        "shadow": "rgba(0, 0, 0, 0.06)",
        "divider": "#E5E7EB",
        "chip_bg": "#F3F4F6",
        "chip_active_bg": "rgba(179, 123, 36, 0.12)",
        "stepper_btn": "#E5E7EB",
        "stepper_btn_hover": "#D1D5DB"
    },
    "dark": {
        "bg_canvas": "#0D0E11",        # Deep Obsidian Noir
        "bg_card": "#16181D",          # Charcoal Glass Card Surface
        "bg_secondary": "#1D2027",      # Elevated Glass Layer
        "bg_subtle": "#242731",
        "text_primary": "#F3F4F6",      # Soft Warm Pearl
        "text_secondary": "#A0A7B5",    # Slate Mist
        "text_muted": "#868E9E",        # Muted Subtext
        "accent": "#C59A4E",           # Calming Muted Champagne Gold
        "accent_hover": "#D8AA5A",
        "accent_subtle": "rgba(197, 154, 78, 0.12)",
        "border": "#23262F",
        "border_subtle": "rgba(255, 255, 255, 0.06)",
        "border_active": "#C59A4E",
        "gold": "#C59A4E",
        "btn_text": "#0D0E11",
        "shadow": "rgba(0, 0, 0, 0.45)",
        "divider": "rgba(255, 255, 255, 0.08)",
        "chip_bg": "#1D2027",
        "chip_active_bg": "rgba(197, 154, 78, 0.14)",
        "stepper_btn": "#23262F",
        "stepper_btn_hover": "#2E323D"
    }
}


def get_popup_qss(is_dark: bool = False) -> str:
    """Returns the QSS stylesheet for the Centered Scripture Pop-up Card."""
    c = THEMES["dark"] if is_dark else THEMES["light"]
    
    return f"""
    QWidget#PopupCardRoot {{
        background-color: {c["bg_card"]};
        border: 1px solid {c["border"]};
        border-radius: 12px;
        font-family: '.AppleSystemUIFont', 'Helvetica Neue', 'Helvetica', sans-serif;
    }}
    
    QLabel#ThemeBadge {{
        background-color: {c["accent_subtle"]};
        color: {c["accent"]};
        border: 1px solid {c["accent"]};
        border-radius: 10px;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 10px;
        letter-spacing: 0.6px;
    }}
    
    QLabel#TranslationBadge {{
        background-color: {c["bg_secondary"]};
        color: {c["text_secondary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        font-size: 11.5px;
        font-weight: 700;
        padding: 3px 9px;
    }}

    QLabel#ScriptureReference {{
        font-size: 15px;
        font-weight: 700;
        color: {c["text_primary"]};
        letter-spacing: -0.2px;
        background: transparent;
        border: none;
    }}
    
    QTextBrowser, QTextBrowser#ScriptureText, QTextBrowser#ScriptureTextBrowser {{
        background-color: transparent;
        background: transparent;
        border: none;
        color: {c["text_primary"]};
        selection-background-color: {c["accent_subtle"]};
        selection-color: {c["accent"]};
    }}
    
    QPushButton#PinButton {{
        background-color: {c["bg_secondary"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 7px 16px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#PinButton:hover {{
        background-color: {c["bg_subtle"]};
        border-color: {c["accent"]};
        color: {c["text_primary"]};
    }}
    
    QPushButton#PinButtonActive {{
        background-color: {c["accent_subtle"]};
        color: {c["accent"]};
        border: 1.5px solid {c["accent"]};
        border-radius: 8px;
        font-size: 12px;
        font-weight: 700;
        padding: 6px 14px;
    }}
    
    QPushButton#TransCycleBtn {{
        background-color: {c["bg_secondary"]};
        color: {c["text_secondary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        padding: 6px 14px;
    }}
    QPushButton#TransCycleBtn:hover {{
        color: {c["text_primary"]};
        border-color: {c["accent"]};
        background-color: {c["bg_subtle"]};
    }}
    
    QPushButton#DismissBtn {{
        background-color: transparent;
        color: {c["text_muted"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 6px 16px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#DismissBtn:hover {{
        color: {c["text_primary"]};
        border-color: {c["text_secondary"]};
        background-color: {c["bg_secondary"]};
    }}
    """



def get_control_panel_qss(is_dark: bool = True) -> str:
    """Returns the QSS stylesheet for the Welcome & Settings Control Panel Window."""
    c = THEMES["dark"] if is_dark else THEMES["light"]
    
    return f"""
    QDialog#ControlPanelWindow {{
        background-color: {c["bg_canvas"]};
        color: {c["text_primary"]};
        font-family: '.AppleSystemUIFont', 'Helvetica Neue', 'Helvetica', sans-serif;
    }}
    
    QFrame#CardSurface {{
        background-color: {c["bg_card"]};
        border: 1px solid {c["border"]};
        border-radius: 12px;
    }}
    
    QLabel#PanelHeaderTitle {{
        color: {c["text_primary"]};
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }}
    
    QLabel#PanelHeaderSubtitle {{
        color: {c["text_muted"]};
        font-size: 13px;
    }}
    
    QLabel#SectionTitle {{
        color: {c["text_secondary"]};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }}
    
    /* Icon-Only 2-Segment Light / Dark Capsule Toggle */
    QFrame#ThemeToggleCapsule {{
        background-color: {c["bg_secondary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
    }}
    QPushButton#ThemeSegActive {{
        background-color: {c["chip_active_bg"]};
        color: {c["accent"]};
        border: 1px solid {c["accent"]};
        border-radius: 6px;
    }}
    QPushButton#ThemeSegInactive {{
        background-color: transparent;
        color: {c["text_muted"]};
        border: 1px solid transparent;
        border-radius: 6px;
    }}
    QPushButton#ThemeSegInactive:hover {{
        color: {c["text_primary"]};
        background-color: {c["bg_subtle"]};
    }}
    
    QLineEdit, QTextEdit {{
        background-color: {c["bg_secondary"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 9px 13px;
        font-size: 13px;
        selection-background-color: {c["accent"]};
        selection-color: #0D0E11;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border: 1px solid {c["accent"]};
        background-color: {c["bg_card"]};
    }}
    
    QCheckBox {{
        font-size: 12.5px;
        font-weight: 500;
        color: {c["text_primary"]};
        spacing: 9px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border-radius: 4px;
        border: 1.5px solid {"#4B5563" if is_dark else "#CBD5E1"};
        background-color: {"#1D2027" if is_dark else "#FFFFFF"};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c["accent"]};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c["accent"]};
        border-color: {c["accent"]};
        image: url({get_icon_path("checkbox_check.png")});
    }}
    QCheckBox::indicator:checked:hover {{
        background-color: {c["accent_hover"]};
        border-color: {c["accent_hover"]};
    }}
    
    /* 4-Segment Bible Translation Bar */
    QPushButton#TransSegment {{
        background-color: {c["bg_secondary"]};
        color: {c["text_secondary"]};
        border: 1px solid {c["border"]};
        padding: 10px 20px;
        font-size: 13px;
        font-weight: 600;
        border-radius: 8px;
    }}
    QPushButton#TransSegment:hover {{
        color: {c["text_primary"]};
        background-color: {c["bg_subtle"]};
        border-color: {c["text_muted"]};
    }}
    QPushButton#TransSegmentSelected {{
        background-color: {c["accent_subtle"]};
        color: {c["accent"]};
        border: 1.5px solid {c["accent"]};
        padding: 10px 20px;
        font-size: 13px;
        font-weight: 700;
        border-radius: 8px;
    }}
    
    /* 5 Flagship Preset Theme Pills */
    QPushButton#ThemePill {{
        background-color: {c["bg_secondary"]};
        color: {c["text_secondary"]};
        border: 1px solid {c["border"]};
        border-radius: 9px;
        padding: 10px 14px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton#ThemePill:hover {{
        border-color: {c["accent"]};
        color: {c["text_primary"]};
        background-color: {c["bg_subtle"]};
    }}
    QPushButton#ThemePillSelected {{
        background-color: {c["chip_active_bg"]};
        color: {c["accent"]};
        border: 1.5px solid {c["accent"]};
        border-radius: 9px;
        padding: 10px 14px;
        font-size: 13px;
        font-weight: 700;
    }}
    
    /* Dedicated Custom Focus Card */
    QFrame#AIExploreCard {{
        background-color: {c["bg_secondary"]};
        border: 1px solid {c["border"]};
        border-radius: 12px;
    }}
    QPushButton#CurateBtn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c["accent"]}, stop:1 {c["accent_hover"]});
        color: {c["btn_text"]};
        border: none;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 700;
        padding: 8px 16px;
    }}
    QPushButton#CurateBtn:hover {{
        background: {c["accent_hover"]};
    }}
    QPushButton#SavedThemeChip {{
        background-color: {c["bg_subtle"]};
        color: {c["text_secondary"]};
        border: 1px solid {c["border"]};
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 11px;
        font-weight: 500;
    }}
    QPushButton#SavedThemeChip:hover {{
        border-color: {c["accent"]};
        color: {c["accent"]};
    }}
    
    /* Stepper Numeric Capsules */
    QFrame#StepperCapsule {{
        background-color: {c["bg_secondary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 3px;
    }}
    QPushButton#StepperBtn {{
        background-color: {c["stepper_btn"]};
        color: {c["text_primary"]};
        border: none;
        border-radius: 6px;
        font-size: 16px;
        font-weight: 700;
        min-width: 36px;
        max-width: 36px;
        min-height: 34px;
        max-height: 34px;
    }}
    QPushButton#StepperBtn:hover {{
        background-color: {c["stepper_btn_hover"]};
        color: {c["accent"]};
    }}
    QPushButton#StepperBtn:disabled {{
        color: {c["text_muted"]};
        background-color: transparent;
    }}
    QLabel#StepperDisplay {{
        color: {c["text_primary"]};
        font-size: 13px;
        font-weight: 600;
        qproperty-alignment: AlignCenter;
    }}
    
    /* Action Buttons */
    QPushButton#PrimaryBtn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c["accent"]}, stop:1 {c["accent_hover"]});
        color: {c["btn_text"]};
        border: none;
        border-radius: 10px;
        padding: 12px 26px;
        font-size: 14px;
        font-weight: 700;
    }}
    QPushButton#PrimaryBtn:hover {{
        background: {c["accent_hover"]};
    }}
    QPushButton#PrimaryBtn:disabled {{
        background: {c["bg_secondary"]};
        color: {c["text_muted"]};
        border: 1px solid {c["border"]};
    }}
    QPushButton#PrimaryActionBtn:hover {{
        background-color: {c["accent_hover"]};
    }}
    
    QPushButton#SecondaryBtn {{
        background-color: {c["bg_secondary"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#SecondaryBtn:hover {{
        color: {c["accent"]};
        border-color: {c["accent"]};
        background-color: {c["bg_subtle"]};
    }}
    
    QComboBox {{
        background-color: {c["bg_secondary"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 12px;
        font-weight: 500;
    }}
    QComboBox:hover {{
        border-color: {c["accent"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c["bg_card"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        selection-background-color: {c["chip_active_bg"]};
        selection-color: {c["accent"]};
        padding: 4px;
    }}
    
    QPushButton#SecondaryActionBtn {{
        background-color: {c["bg_subtle"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 10px 18px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton#SecondaryActionBtn:hover {{
        border-color: {c["text_muted"]};
    }}
    
    /* Tabs */
    QTabWidget::pane {{
        border: 1px solid {c["border"]};
        border-radius: 8px;
        background: {c["bg_card"]};
        padding: 12px;
    }}
    QTabBar::tab {{
        background: {c["bg_secondary"]};
        color: {c["text_muted"]};
        border: 1px solid {c["border"]};
        border-bottom: none;
        padding: 8px 18px;
        margin-right: 4px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {c["bg_card"]};
        color: {c["accent"]};
        border-top: 2px solid {c["accent"]};
    }}
    
    /* List Widget for Pinned Verses Archive */
    QListWidget {{
        background-color: {c["bg_card"]};
        border: 1px solid {c["border"]};
        border-radius: 10px;
        padding: 8px;
        color: {c["text_primary"]};
        outline: none;
    }}
    QListWidget::item {{
        background-color: {c["bg_secondary"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 8px;
        color: {c["text_primary"]};
        font-size: 13px;
        line-height: 1.6;
    }}
    QListWidget::item:hover {{
        background-color: {c["chip_active_bg"]};
        border-color: {c["accent"]};
    }}
    QListWidget::item:selected {{
        background-color: {c["accent_subtle"]};
        border: 1px solid {c["accent"]};
        color: {c["text_primary"]};
    }}
    """


def _strip_wrapping_quotes(t: str) -> str:
    t = t.strip()
    if (t.startswith('"') and t.endswith('"')) or (t.startswith('“') and t.endswith('”')):
        t = t[1:-1].strip()
    return t


def format_scripture_html(text: str, reference: str, is_dark: bool = False, verses=None) -> str:
    """
    Formats Scripture text with breathable line height and dynamic sizing.

    Single verse: rendered as clean flowing text.
    Multi-verse passage (pass `verses` as an ordered list of (verse_no, text)):
    rendered as one continuous passage with small superscript verse numbers, so the
    reader can see it is connected scripture without it fragmenting into a list.
    """
    c = THEMES["dark"] if is_dark else THEMES["light"]

    is_passage = bool(verses) and len(verses) > 1

    if is_passage:
        length = sum(len(t) for _, t in verses)
    else:
        length = len(_strip_wrapping_quotes(text))

    # Dynamic typography: shrink slightly as the passage grows so it always breathes.
    if length > 520:
        font_size, line_height = "13.5px", "1.75"
    elif length > 350:
        font_size, line_height = "14.5px", "1.8"
    elif length > 160:
        font_size, line_height = "15.5px", "1.8"
    else:
        font_size, line_height = "17px", "1.8"

    if is_passage:
        num_color = c["accent"]
        parts = []
        for vnum, vtext in verses:
            vt = _strip_wrapping_quotes(vtext)
            parts.append(
                f'<sup style="color:{num_color}; font-size:0.68em; font-weight:700; '
                f'padding-right:2px; vertical-align:super;">{vnum}</sup>{vt}'
            )
        body = " ".join(parts)
    else:
        body = _strip_wrapping_quotes(text)

    return f"""
    <div style="font-family: '.AppleSystemUIFont', 'Helvetica Neue', 'Helvetica', sans-serif; padding: 4px 2px;">
        <div style="font-size: {font_size}; line-height: {line_height}; color: {c['text_primary']}; font-weight: 400; letter-spacing: 0.2px;">
            {body}
        </div>
    </div>
    """
