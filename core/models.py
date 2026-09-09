"""
Scriptaz Dynamic Data Models
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class BibleTranslation(str, Enum):
    KJV = "KJV"
    NLT = "NLT"
    NKJV = "NKJV"
    ESV = "ESV"


class ScriptureTheme(str, Enum):
    PEACE = "Peace"
    WISDOM = "Wisdom"
    FAITH = "Faith"
    GRACE = "Grace"
    PROVISION = "Provision"
    CUSTOM = "Custom"


class CustomThemeModel(BaseModel):
    id: Optional[int] = None
    title: str
    user_prompt: str
    theological_summary: Optional[str] = None
    semantic_anchors: List[str] = Field(default_factory=list)
    seed_references: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: Optional[datetime] = None


class VerseModel(BaseModel):
    id: Optional[int] = None
    book: str
    chapter: int
    verse: int
    reference: str  # e.g., "Luke 10:19" or "Ephesians 1:17-20"
    translation: BibleTranslation = BibleTranslation.KJV
    text: str
    theme: ScriptureTheme = ScriptureTheme.FAITH
    surrounding_context: Optional[str] = None
    key_original_words: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class UserSettingsModel(BaseModel):
    user_name: str = Field(default="Friend", max_length=50)
    interval_minutes: int = Field(default=60, ge=30, le=120)
    daily_limit: int = Field(default=5, ge=1, le=10)
    active_translation: BibleTranslation = BibleTranslation.NKJV
    active_theme: ScriptureTheme = ScriptureTheme.PEACE
    active_custom_theme_id: Optional[int] = None
    active_custom_theme_title: Optional[str] = None
    personal_context: str = Field(default="", max_length=1000)
    launch_on_startup: bool = False
    dark_mode: bool = False
    has_completed_onboarding: bool = False
    run_in_background: bool = True

    @property
    def preferred_bible_version(self) -> str:
        return self.active_translation.value if hasattr(self.active_translation, 'value') else str(self.active_translation)

    @property
    def personal_struggle_context(self) -> str:
        return self.personal_context


class PinnedVerseModel(BaseModel):
    id: Optional[int] = None
    verse_id: int
    reference: str
    translation: BibleTranslation
    text: str
    theme: ScriptureTheme
    pinned_at: datetime
    days_remaining: int = 7
    is_active_cycle: bool = True
    notes: Optional[str] = None


class QueueItemModel(BaseModel):
    id: Optional[int] = None
    verse: VerseModel
    sequence_order: int
    is_shown: bool = False
    is_pinned: bool = False
    shown_at: Optional[datetime] = None
