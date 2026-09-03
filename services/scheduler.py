"""
Scriptaz Cross-Platform Active-Time Workday Scheduler Engine
Tracks real keyboard/mouse input on macOS and Windows, pauses when user is away/locked,
implements 60/40 pinned rotation, and executes infinite workday cycle rollover.
"""

import sys
import time
import ctypes
import platform
from datetime import datetime, date
from typing import Optional, Callable
from PySide6.QtCore import QObject, QTimer, Signal

from core.db import db
from core.models import VerseModel, UserSettingsModel

# Idle threshold: 120 seconds of no keyboard/mouse input = paused
IDLE_THRESHOLD_SECONDS = 120


def get_system_idle_seconds() -> float:
    """Returns the seconds elapsed since last keyboard/mouse event on macOS or Windows."""
    system = platform.system()

    if system == "Darwin":
        try:
            # Native macOS Quartz event source check via ctypes
            import ctypes.util
            core_graphics = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
            # kCGIEventSourceStateCombinedSessionState = 0
            seconds = core_graphics.CGEventSourceSecondsSinceLastInputEvent(0)
            return float(seconds)
        except Exception:
            return 0.0

    elif system == "Windows":
        try:
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            millis_since_boot = ctypes.windll.kernel32.GetTickCount()
            idle_millis = millis_since_boot - lii.dwTime
            return max(0.0, idle_millis / 1000.0)
        except Exception:
            return 0.0

    return 0.0


class WorkdayScheduler(QObject):
    """
    Intelligent active-time scheduler that accumulates real working minutes,
    pauses during breaks/meetings, and triggers scripture drops on cycle.
    """
    verse_trigger_signal = Signal(dict)          # Emits verse dict when due
    status_updated_signal = Signal(dict)         # Emits status dict for UI

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings: UserSettingsModel = db.get_user_settings()
        
        self.is_paused: bool = False
        self.active_seconds_accumulated: int = 0
        self.verses_delivered_today: int = 0
        self.current_cycle_number: int = 1
        self.current_date: date = datetime.now().date()
        self.last_drop_timestamp: float = time.time()
        self.drop_counter: int = 0               # Used for 60/40 pinned vs fresh rotation
        
        self.heartbeat_timer: Optional[QTimer] = None

    def start(self):
        """Starts or restarts the 1-second heartbeat timer once QApplication is running."""
        if self.heartbeat_timer is None:
            self.heartbeat_timer = QTimer(self)
            self.heartbeat_timer.timeout.connect(self._tick)
        if not self.heartbeat_timer.isActive():
            self.heartbeat_timer.start(1000)
        self._emit_status()

    def reload_settings(self):
        """Reloads settings from SQLite."""
        self.settings = db.get_user_settings()
        target_seconds = max(60, self.settings.interval_minutes * 60)
        if self.active_seconds_accumulated > target_seconds:
            self.active_seconds_accumulated = target_seconds
        self._emit_status()

    def set_paused(self, paused: bool):
        """Pauses or resumes active-time tracking."""
        self.is_paused = paused
        self._emit_status()

    def trigger_now(self):
        """Instantly drops the next scripture on user demand."""
        self._deliver_scripture(force_fresh=True)

    def _tick(self):
        """Called every second to track active time."""
        # Midnight Day Rollover: reset daily count if a new day has arrived
        today = datetime.now().date()
        if today != self.current_date:
            self.current_date = today
            self.verses_delivered_today = 0
            self.current_cycle_number = 1

        if self.is_paused:
            self._emit_status(state="Paused")
            return

        idle_sec = get_system_idle_seconds()
        if idle_sec >= IDLE_THRESHOLD_SECONDS:
            # User is away from desk / screen locked -> pause accumulation
            self._emit_status(state="Away")
            return

        # User is actively working
        self.active_seconds_accumulated += 1
        
        target_seconds = max(60, self.settings.interval_minutes * 60)
        if self.active_seconds_accumulated >= target_seconds:
            self._deliver_scripture(force_fresh=False)
            return

        self._emit_status(state="Active")

    def _deliver_scripture(self, force_fresh: bool = False):
        """Pulls the next verse using 60/40 pinned priority and emits signal."""
        self.active_seconds_accumulated = 0
        self.drop_counter += 1
        self.verses_delivered_today += 1

        # Infinite cycle rollover: if daily limit reached, advance cycle
        if self.verses_delivered_today > self.settings.daily_limit:
            self.verses_delivered_today = 1
            self.current_cycle_number += 1

        # 60/40 Rotation: Every 3rd drop attempts to draw from pinned verses (automatic drops only)
        pinned_verses = db.get_pinned_verses()
        verse_data = None

        if not force_fresh and pinned_verses and (self.drop_counter % 3 == 0):
            pinned_idx = (self.drop_counter // 3) % len(pinned_verses)
            pv = pinned_verses[pinned_idx]
            verse_data = {
                "id": pv.verse_id,
                "reference": pv.reference,
                "translation": pv.translation.value if hasattr(pv.translation, 'value') else str(pv.translation),
                "text": pv.text,
                "theme": pv.theme.value if hasattr(pv.theme, 'value') else str(pv.theme),
                "notes": pv.notes
            }

        if not verse_data:
            verse_data = db.get_next_verse_for_user(
                theme=self.settings.active_theme,
                translation=self.settings.active_translation
            )

        # Fallback if queue returned None
        if not verse_data:
            verse_data = {
                "id": 1,
                "reference": "Philippians 4:6-7",
                "translation": self.settings.active_translation.value if hasattr(self.settings.active_translation, 'value') else str(self.settings.active_translation),
                "text": "Be anxious for nothing, but in everything by prayer and supplication, with thanksgiving, let your requests be made known to God; and the peace of God, which surpasses all understanding, will guard your hearts and minds through Christ Jesus.",
                "theme": "Peace"
            }

        self.last_drop_timestamp = time.time()
        self.verse_trigger_signal.emit(verse_data)
        self._emit_status(state="Delivered")

    def get_current_status(self) -> dict:
        """Returns the current real-time state dict synchronously."""
        target_seconds = max(60, self.settings.interval_minutes * 60)
        remaining_seconds = max(0, target_seconds - self.active_seconds_accumulated)
        if self.is_paused:
            state = "Paused"
        elif get_system_idle_seconds() >= IDLE_THRESHOLD_SECONDS:
            state = "Away"
        else:
            state = "Active"

        return {
            "state": state,
            "is_paused": self.is_paused,
            "is_idle": (state == "Away"),
            "active_seconds_accumulated": self.active_seconds_accumulated,
            "target_seconds": target_seconds,
            "remaining_seconds": remaining_seconds,
            "remaining_minutes": max(1, remaining_seconds // 60) if remaining_seconds > 0 else 0,
            "verses_delivered_today": self.verses_delivered_today,
            "daily_limit": self.settings.daily_limit,
            "current_cycle": self.current_cycle_number,
            "active_theme": self.settings.active_theme,
            "preferred_version": self.settings.preferred_bible_version
        }

    def _emit_status(self, state: Optional[str] = None):
        """Emits current timing and cycle metrics to the UI."""
        status = self.get_current_status()
        if state:
            status["state"] = state
            status["is_idle"] = (state == "Away")
        self.status_updated_signal.emit(status)


scheduler = WorkdayScheduler()

