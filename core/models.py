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
    SIN_AND_GRACE = "Sin & Grace"
    NEW_BIRTH = "New Birth"
    AUTHORITY = "Authority"
    FAITH = "Faith"
    PEACE = "Peace"
    HEALING = "Healing"
    WISDOM = "Wisdom"
    PROVISION_AND_DILIGENCE = "Provision & Diligence"
    SALVATION = "Salvation"
    LOVE = "Love"
    JOY = "Joy"


class VerseModel(BaseModel):
    id: Optional[int] = None
    book: str
    chapter: int
    verse: int
    reference: str  # e.g., "Luke 10:19"
    translation: BibleTranslation = BibleTranslation.KJV
    text: str
    theme: ScriptureTheme
    surrounding_context: Optional[str] = None
    key_original_words: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class UserSettingsModel(BaseModel):
    user_name: str = Field(default="Avidan", max_length=50)
    interval_minutes: int = Field(default=60, ge=30, le=120)
    daily_limit: int = Field(default=5, ge=1, le=10)
    active_translation: BibleTranslation = BibleTranslation.KJV
    active_theme: ScriptureTheme = ScriptureTheme.SIN_AND_GRACE
    personal_context: str = Field(default="", max_length=1000)
    launch_on_startup: bool = False
    dark_mode: bool = True


class InsightRequest(BaseModel):
    verse_id: Optional[int] = None
    reference: str
    translation: BibleTranslation
    verse_text: str
    surrounding_context: Optional[str] = None
    active_theme: str
    personal_context: Optional[str] = None
    user_name: Optional[str] = None


class StructuredInsight(BaseModel):
    context_and_setting: str = ""
    original_word_illumination: str = ""
    christ_centered_revelation: str
    connected_scriptures: List[str] = Field(default_factory=list)
    is_cached: bool = False
    model_used: Optional[str] = None
    cached_at: Optional[datetime] = None


class PinnedVerseModel(BaseModel):
    id: Optional[int] = None
    verse_id: int
    reference: str
    translation: BibleTranslation
    text: str
    theme: ScriptureTheme
    pinned_at: datetime
    notes: Optional[str] = None


class QueueItemModel(BaseModel):
    id: Optional[int] = None
    verse: VerseModel
    sequence_order: int
    is_shown: bool = False
    is_pinned: bool = False
    shown_at: Optional[datetime] = None
