"""
Scriptaz SQLite Database Engine
Provides thread-safe local data storage, multi-translation verse queries,
$0-cost Deep Insight caching, Strong's lexicon lookups, and active-time workday queues.
"""

import sqlite3
import hashlib
import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from core.config import config
from core.models import (
    VerseModel,
    BibleTranslation,
    ScriptureTheme,
    UserSettingsModel,
    CustomThemeModel,
    PinnedVerseModel,
    QueueItemModel
)


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        """Initializes all required SQLite tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Verses Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS verses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book TEXT NOT NULL,
                    chapter INTEGER NOT NULL,
                    verse INTEGER NOT NULL,
                    reference TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    text TEXT NOT NULL,
                    theme TEXT NOT NULL,
                    surrounding_context TEXT,
                    key_original_words TEXT,
                    tags TEXT,
                    embedding_blob BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(reference, translation)
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_verses_theme ON verses(theme, translation);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(reference);")

            # 2. User Settings Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

            # 4. Pinned Verses Table (7-Day Active Cycle + Permanent Memory)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pinned_verses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    verse_id INTEGER NOT NULL,
                    notes TEXT,
                    is_active_cycle INTEGER DEFAULT 1,
                    pinned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (verse_id) REFERENCES verses(id) ON DELETE CASCADE,
                    UNIQUE(verse_id)
                );
            """)
            # Migration check for existing pinned_verses tables
            cursor.execute("PRAGMA table_info(pinned_verses);")
            pv_cols = [r["name"] for r in cursor.fetchall()]
            if "is_active_cycle" not in pv_cols:
                cursor.execute("ALTER TABLE pinned_verses ADD COLUMN is_active_cycle INTEGER DEFAULT 1;")

            # 5. Custom Themes Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    user_prompt TEXT NOT NULL,
                    theological_summary TEXT,
                    semantic_anchors TEXT NOT NULL,
                    seed_references TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 6. Custom Theme Shown History (for continuous, non-repeating stream)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_theme_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    theme_id INTEGER NOT NULL,
                    verse_id INTEGER NOT NULL,
                    shown_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (theme_id) REFERENCES custom_themes(id) ON DELETE CASCADE,
                    FOREIGN KEY (verse_id) REFERENCES verses(id) ON DELETE CASCADE,
                    UNIQUE(theme_id, verse_id)
                );
            """)

            # 7. Active Workday Queue Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day_date TEXT NOT NULL,
                    verse_id INTEGER NOT NULL,
                    sequence_order INTEGER NOT NULL,
                    is_shown INTEGER DEFAULT 0,
                    shown_at TIMESTAMP,
                    FOREIGN KEY (verse_id) REFERENCES verses(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_day ON active_queue(day_date, is_shown);")

            # 8. Theme Rotation Memory (cross-day, ALL themes: preset & custom)
            # theme_key is 'preset:<Name>' or 'custom:<id>' so every theme rotates
            # through its whole pool without repeating, then resets when exhausted.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS theme_history (
                    theme_key TEXT NOT NULL,
                    verse_id INTEGER NOT NULL,
                    shown_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (theme_key, verse_id)
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_theme_history ON theme_history(theme_key);")

            conn.commit()

    def insert_verse(self, verse: VerseModel) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO verses (
                    book, chapter, verse, reference, translation, text, theme,
                    surrounding_context, key_original_words, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reference, translation) DO UPDATE SET
                    text = excluded.text,
                    theme = excluded.theme,
                    surrounding_context = excluded.surrounding_context,
                    key_original_words = excluded.key_original_words,
                    tags = excluded.tags
            """, (
                verse.book,
                verse.chapter,
                verse.verse,
                verse.reference,
                verse.translation.value if hasattr(verse.translation, 'value') else str(verse.translation),
                verse.text,
                verse.theme.value if hasattr(verse.theme, 'value') else str(verse.theme),
                verse.surrounding_context,
                verse.key_original_words,
                json.dumps(verse.tags or [])
            ))
            conn.commit()
            return cursor.lastrowid

    def get_verse_by_id(self, verse_id: int) -> Optional[VerseModel]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM verses WHERE id = ?", (verse_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_verse(row)

    @staticmethod
    def parse_reference(reference: str) -> Optional[Tuple[str, int, int, int]]:
        """Parses reference strings like 'John 3:16', 'Ephesians 1:17-20', or 'Judges 6:14–16' into (book, chapter, start_v, end_v)."""
        if not reference:
            return None
        # Normalize all Unicode dash types (en-dash, em-dash, minus, hyphen) to standard '-'
        clean_ref = re.sub(r"[–—−‐―]", "-", reference.strip())
        # Normalize internal whitespace around colons and hyphens
        clean_ref = re.sub(r"\s*:\s*", ":", clean_ref)
        clean_ref = re.sub(r"\s*-\s*", "-", clean_ref)
        
        match = re.match(r"^([1-3]?[A-Za-z\s]+)\s+(\d+):(\d+)(?:-(\d+))?$", clean_ref)
        if not match:
            return None
        book = match.group(1).strip().title()
        chap = int(match.group(2))
        start_v = int(match.group(3))
        end_v = int(match.group(4)) if match.group(4) else start_v
        return book, chap, start_v, end_v

    def get_verse_by_ref(self, reference: str, translation: str = "KJV") -> Optional[VerseModel]:
        """Retrieves a single verse or multi-verse passage (e.g. 'Ephesians 1:17-20')."""
        trans_val = translation.value if hasattr(translation, 'value') else str(translation)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Try exact single-verse match
            cursor.execute("SELECT * FROM verses WHERE reference = ? AND translation = ?", (reference, trans_val))
            row = cursor.fetchone()
            if row:
                return self._row_to_verse(row)

            # 2. Check for multi-verse range
            parsed = self.parse_reference(reference)
            if not parsed:
                return None
            book, chap, start_v, end_v = parsed
            cursor.execute("""
                SELECT * FROM verses
                WHERE book = ? AND chapter = ? AND verse >= ? AND verse <= ? AND translation = ?
                ORDER BY verse ASC
            """, (book, chap, start_v, end_v, trans_val))
            rows = cursor.fetchall()
            if not rows:
                return None

            first_row = rows[0]
            combined_text = " ".join(r["text"] for r in rows)
            first_verse = self._row_to_verse(first_row)
            first_verse.reference = f"{book} {chap}:{start_v}-{end_v}" if start_v != end_v else f"{book} {chap}:{start_v}"
            first_verse.text = combined_text
            return first_verse

    def get_verses_by_theme(self, theme: str, translation: str = "KJV") -> List[VerseModel]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM verses WHERE (theme = ? OR tags LIKE ?) AND translation = ? ORDER BY id ASC",
                (theme, f"%{theme}%", translation)
            )
            rows = cursor.fetchall()
            if not rows:
                cursor.execute(
                    "SELECT * FROM verses WHERE translation = ? ORDER BY id ASC LIMIT 50",
                    (translation,)
                )
                rows = cursor.fetchall()
            return [self._row_to_verse(r) for r in rows]

    def get_next_verse_for_user(self, theme: str = "Wisdom", translation: str = "NLT") -> Optional[Dict]:
        """Pulls the next unread or relevant verse for the active theme and preferred translation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            theme_val = theme.value if hasattr(theme, 'value') else str(theme)
            trans_val = translation.value if hasattr(translation, 'value') else str(translation)
            
            cursor.execute("""
                SELECT id, book, chapter, verse, reference, translation, text, theme
                FROM verses
                WHERE theme = ? AND translation = ?
                ORDER BY RANDOM()
                LIMIT 1
            """, (theme_val, trans_val))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    SELECT id, book, chapter, verse, reference, translation, text, theme
                    FROM verses
                    WHERE translation = ?
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (trans_val,))
                row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_translations_for_ref(self, reference: str) -> Dict[str, str]:
        """Returns 4-way translation text for a single verse or multi-verse range (e.g. 'Ephesians 1:17-20')."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Try exact match
            cursor.execute("SELECT translation, text FROM verses WHERE reference = ?", (reference,))
            rows = cursor.fetchall()
            if rows:
                return {r["translation"]: r["text"] for r in rows}

            # 2. Check for multi-verse range
            parsed = self.parse_reference(reference)
            if not parsed:
                return {}
            book, chap, start_v, end_v = parsed
            cursor.execute("""
                SELECT translation, verse, text
                FROM verses
                WHERE book = ? AND chapter = ? AND verse >= ? AND verse <= ?
                ORDER BY translation, verse ASC
            """, (book, chap, start_v, end_v))
            rows = cursor.fetchall()
            
            results = {}
            for r in rows:
                results.setdefault(r["translation"], []).append(r["text"])
                
            return {
                trans: " ".join(v_list)
                for trans, v_list in results.items()
            }

    def count_verses(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM verses")
            return cursor.fetchone()["count"]

    def get_settings(self) -> UserSettingsModel:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_settings")
            rows = dict(cursor.fetchall())
            
            raw_theme = rows.get("active_theme", "Peace")
            valid_themes = [t.value for t in ScriptureTheme]
            active_theme = ScriptureTheme(raw_theme) if raw_theme in valid_themes else ScriptureTheme.PEACE

            custom_id_val = rows.get("active_custom_theme_id")
            active_custom_id = int(custom_id_val) if custom_id_val and custom_id_val.isdigit() else None

            return UserSettingsModel(
                user_name=rows.get("user_name", "Friend"),
                interval_minutes=int(rows.get("interval_minutes", str(config.default_interval_minutes))),
                daily_limit=int(rows.get("daily_limit", str(config.default_daily_limit))),
                active_translation=BibleTranslation(rows.get("active_translation", "NKJV")),
                active_theme=active_theme,
                active_custom_theme_id=active_custom_id,
                active_custom_theme_title=rows.get("active_custom_theme_title"),
                personal_context=rows.get("personal_context", ""),
                launch_on_startup=rows.get("launch_on_startup", "false").lower() == "true",
                dark_mode=rows.get("dark_mode", "false").lower() == "true",
                has_completed_onboarding=rows.get("has_completed_onboarding", "false").lower() == "true",
                run_in_background=rows.get("run_in_background", "true").lower() == "true"
            )

    def get_user_settings(self) -> UserSettingsModel:
        return self.get_settings()

    def save_user_settings(self, settings: UserSettingsModel):
        return self.update_settings(settings)

    def update_settings(self, settings: UserSettingsModel):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            settings_dict = {
                "user_name": settings.user_name,
                "interval_minutes": str(settings.interval_minutes),
                "daily_limit": str(settings.daily_limit),
                "active_translation": settings.active_translation.value if hasattr(settings.active_translation, 'value') else str(settings.active_translation),
                "active_theme": settings.active_theme.value if hasattr(settings.active_theme, 'value') else str(settings.active_theme),
                "active_custom_theme_id": str(settings.active_custom_theme_id) if settings.active_custom_theme_id else "",
                "active_custom_theme_title": settings.active_custom_theme_title or "",
                "personal_context": settings.personal_context,
                "launch_on_startup": str(settings.launch_on_startup).lower(),
                "dark_mode": str(settings.dark_mode).lower(),
                "has_completed_onboarding": str(settings.has_completed_onboarding).lower(),
                "run_in_background": str(settings.run_in_background).lower()
            }
            for k, v in settings_dict.items():
                cursor.execute(
                    "INSERT INTO user_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (k, v)
                )
            conn.commit()

    # ----------------------------------------------------------------------
    # Custom Themes Engine Methods
    # ----------------------------------------------------------------------
    def save_custom_theme(
        self,
        title: str,
        user_prompt: str,
        theological_summary: Optional[str] = None,
        semantic_anchors: Optional[List[str]] = None,
        seed_references: Optional[List[str]] = None,
        is_active: bool = True
    ) -> int:
        """Stores a new custom theme and sets it active."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if is_active:
                cursor.execute("UPDATE custom_themes SET is_active = 0")
            
            cursor.execute("""
                INSERT INTO custom_themes (
                    title, user_prompt, theological_summary, semantic_anchors, seed_references, is_active
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                title,
                user_prompt,
                theological_summary or "",
                json.dumps(semantic_anchors or []),
                json.dumps(seed_references or []),
                1 if is_active else 0
            ))
            theme_id = cursor.lastrowid
            
            if is_active:
                cursor.execute(
                    "INSERT INTO user_settings (key, value) VALUES ('active_theme', 'Custom'), ('active_custom_theme_id', ?), ('active_custom_theme_title', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (str(theme_id), title)
                )
            conn.commit()
            return theme_id

    def get_active_custom_theme(self) -> Optional[CustomThemeModel]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM custom_themes WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            return CustomThemeModel(
                id=row["id"],
                title=row["title"],
                user_prompt=row["user_prompt"],
                theological_summary=row["theological_summary"],
                semantic_anchors=json.loads(row["semantic_anchors"]) if row["semantic_anchors"] else [],
                seed_references=json.loads(row["seed_references"]) if row["seed_references"] else [],
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            )

    def get_custom_theme(self, theme_id: int) -> Optional[CustomThemeModel]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM custom_themes WHERE id = ? LIMIT 1", (theme_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return CustomThemeModel(
                id=row["id"],
                title=row["title"],
                user_prompt=row["user_prompt"],
                theological_summary=row["theological_summary"],
                semantic_anchors=json.loads(row["semantic_anchors"]) if row["semantic_anchors"] else [],
                seed_references=json.loads(row["seed_references"]) if row["seed_references"] else [],
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            )

    def get_all_custom_themes(self) -> List[CustomThemeModel]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM custom_themes ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [
                CustomThemeModel(
                    id=r["id"],
                    title=r["title"],
                    user_prompt=r["user_prompt"],
                    theological_summary=r["theological_summary"],
                    semantic_anchors=json.loads(r["semantic_anchors"]) if r["semantic_anchors"] else [],
                    seed_references=json.loads(r["seed_references"]) if r["seed_references"] else [],
                    is_active=bool(r["is_active"]),
                    created_at=datetime.fromisoformat(r["created_at"]) if r["created_at"] else None
                )
                for r in rows
            ]

    def activate_custom_theme(self, theme_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM custom_themes WHERE id = ?", (theme_id,))
            row = cursor.fetchone()
            if not row:
                return False
            title = row["title"]
            cursor.execute("UPDATE custom_themes SET is_active = 0")
            cursor.execute("UPDATE custom_themes SET is_active = 1 WHERE id = ?", (theme_id,))
            cursor.execute(
                "INSERT INTO user_settings (key, value) VALUES ('active_theme', 'Custom'), ('active_custom_theme_id', ?), ('active_custom_theme_title', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(theme_id), title)
            )
            conn.commit()
            return True

    def delete_custom_theme(self, theme_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_settings WHERE key = 'active_custom_theme_id'")
            row = cursor.fetchone()
            if row and row["value"] == str(theme_id):
                cursor.execute("UPDATE user_settings SET value = 'Peace' WHERE key = 'active_theme'")
                cursor.execute("UPDATE user_settings SET value = '' WHERE key = 'active_custom_theme_id'")
                cursor.execute("UPDATE user_settings SET value = '' WHERE key = 'active_custom_theme_title'")
            cursor.execute("DELETE FROM custom_themes WHERE id = ?", (theme_id,))
            cursor.execute("DELETE FROM custom_theme_history WHERE theme_id = ?", (theme_id,))
            conn.commit()
            return cursor.rowcount > 0

    def record_custom_theme_shown(self, theme_id: int, verse_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO custom_theme_history (theme_id, verse_id) VALUES (?, ?)
                ON CONFLICT(theme_id, verse_id) DO UPDATE SET shown_at = CURRENT_TIMESTAMP
            """, (theme_id, verse_id))
            conn.commit()

    def get_custom_theme_shown_verse_ids(self, theme_id: int) -> set:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT verse_id FROM custom_theme_history WHERE theme_id = ?", (theme_id,))
            return set(r["verse_id"] for r in cursor.fetchall())

    # ----------------------------------------------------------------------
    # Pinned Verses: 7-Day Active Cycle & Permanent Memory Archive
    # ----------------------------------------------------------------------
    def pin_verse(self, verse_id: int, notes: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pinned_verses (verse_id, notes, is_active_cycle, pinned_at)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(verse_id) DO UPDATE SET
                    is_active_cycle = 1,
                    pinned_at = CURRENT_TIMESTAMP,
                    notes = COALESCE(excluded.notes, pinned_verses.notes)
            """, (verse_id, notes))
            conn.commit()
            return True

    def unpin_verse(self, verse_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pinned_verses WHERE verse_id = ?", (verse_id,))
            conn.commit()
            return cursor.rowcount > 0

    def is_verse_pinned(self, verse_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM pinned_verses WHERE verse_id = ?", (verse_id,))
            return cursor.fetchone() is not None

    def get_active_pinned_verses(self, max_days: int = 7) -> List[PinnedVerseModel]:
        """Returns pinned verses currently within the 7-day active daily anchor cycle."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pv.id as pin_id, pv.verse_id, pv.notes, pv.pinned_at,
                       v.reference, v.translation, v.text, v.theme
                FROM pinned_verses pv
                JOIN verses v ON pv.verse_id = v.id
                WHERE pv.is_active_cycle = 1
                ORDER BY pv.pinned_at DESC
            """)
            rows = cursor.fetchall()
            result = []
            now = datetime.now()
            for r in rows:
                p_date = datetime.fromisoformat(r["pinned_at"]) if r["pinned_at"] else now
                days_elapsed = (now - p_date).days
                days_left = max(0, max_days - days_elapsed)
                if days_left > 0:
                    result.append(PinnedVerseModel(
                        id=r["pin_id"],
                        verse_id=r["verse_id"],
                        reference=r["reference"],
                        translation=BibleTranslation(r["translation"]),
                        text=r["text"],
                        theme=ScriptureTheme(r["theme"]) if r["theme"] in [t.value for t in ScriptureTheme] else ScriptureTheme.FAITH,
                        pinned_at=p_date,
                        days_remaining=days_left,
                        is_active_cycle=True,
                        notes=r["notes"]
                    ))
            return result

    def get_pinned_archive(self) -> List[PinnedVerseModel]:
        """Returns the full permanent archive of all pinned verses."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pv.id as pin_id, pv.verse_id, pv.notes, pv.pinned_at,
                       v.reference, v.translation, v.text, v.theme
                FROM pinned_verses pv
                JOIN verses v ON pv.verse_id = v.id
                ORDER BY pv.pinned_at DESC
            """)
            rows = cursor.fetchall()
            result = []
            now = datetime.now()
            for r in rows:
                p_date = datetime.fromisoformat(r["pinned_at"]) if r["pinned_at"] else now
                days_elapsed = (now - p_date).days
                days_left = max(0, 7 - days_elapsed)
                result.append(PinnedVerseModel(
                    id=r["pin_id"],
                    verse_id=r["verse_id"],
                    reference=r["reference"],
                    translation=BibleTranslation(r["translation"]),
                    text=r["text"],
                    theme=ScriptureTheme(r["theme"]) if r["theme"] in [t.value for t in ScriptureTheme] else ScriptureTheme.FAITH,
                    pinned_at=p_date,
                    days_remaining=days_left,
                    is_active_cycle=days_left > 0,
                    notes=r["notes"]
                ))
            return result

    def get_pinned_verses(self) -> List[PinnedVerseModel]:
        return self.get_pinned_archive()

    # ----------------------------------------------------------------------
    # Passage Intelligence: expand an anchor verse to its natural sense-unit
    # (boundaries precomputed once by scripts/build_passages.py).
    # ----------------------------------------------------------------------
    def get_passage_span(self, book: str, chapter: int, verse: int, translation: str) -> Tuple[int, int]:
        """Returns (start_verse, end_verse) for the passage containing this verse."""
        trans_val = translation.value if hasattr(translation, 'value') else str(translation)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT start_verse, end_verse FROM verse_passage_map
                    WHERE translation = ? AND book = ? AND chapter = ? AND verse = ?
                    LIMIT 1
                """, (trans_val, book, chapter, verse))
                row = cursor.fetchone()
            except sqlite3.OperationalError:
                # Passage map not built yet -> behave as single-verse (safe fallback).
                return (verse, verse)
            if row:
                return (row["start_verse"], row["end_verse"])
            return (verse, verse)

    def get_passage_pieces(self, reference: str, translation: str) -> List[Tuple[int, str]]:
        """Returns ordered [(verse_no, text), ...] for a single verse or a range reference."""
        trans_val = translation.value if hasattr(translation, 'value') else str(translation)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            parsed = self.parse_reference(reference)
            if not parsed:
                cursor.execute(
                    "SELECT verse, text FROM verses WHERE reference = ? AND translation = ? ORDER BY verse ASC",
                    (reference, trans_val)
                )
                return [(r["verse"], r["text"]) for r in cursor.fetchall()]
            book, chap, start_v, end_v = parsed
            cursor.execute("""
                SELECT verse, text FROM verses
                WHERE book = ? AND chapter = ? AND verse >= ? AND verse <= ? AND translation = ?
                ORDER BY verse ASC
            """, (book, chap, start_v, end_v, trans_val))
            return [(r["verse"], r["text"]) for r in cursor.fetchall()]

    def expand_to_passage(self, verse: Optional[VerseModel]) -> Optional[VerseModel]:
        """
        Expands a single anchor verse to its natural passage unit so connected verses
        are shown together for context. Honors an already-curated range as-is, and keeps
        the anchor verse id unchanged so pinning and daily dedup stay stable.
        """
        if not verse:
            return verse
        # Already a range (e.g. an AI-curated seed like 'John 10:11-15') -> honor it.
        if verse.reference and "-" in verse.reference:
            return verse
        trans_val = verse.translation.value if hasattr(verse.translation, 'value') else str(verse.translation)
        start_v, end_v = self.get_passage_span(verse.book, verse.chapter, verse.verse, trans_val)
        if end_v <= start_v:
            return verse
        pieces = self.get_passage_pieces(f"{verse.book} {verse.chapter}:{start_v}-{end_v}", trans_val)
        if len(pieces) <= 1:
            return verse
        verse.reference = f"{verse.book} {verse.chapter}:{start_v}-{end_v}"
        verse.text = " ".join(t for _, t in pieces)
        return verse

    def get_next_queue_verse(self) -> Optional[VerseModel]:
        today_str = date.today().isoformat()
        settings = self.get_settings()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT q.id as queue_id, v.*
                FROM active_queue q
                JOIN verses v ON q.verse_id = v.id
                WHERE q.day_date = ? AND q.is_shown = 0
                ORDER BY q.sequence_order ASC
                LIMIT 1
            """, (today_str,))
            row = cursor.fetchone()

            if row:
                queue_id = row["queue_id"]
                cursor.execute(
                    "UPDATE active_queue SET is_shown = 1, shown_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (queue_id,)
                )
                conn.commit()
                return self.expand_to_passage(self._row_to_verse(row))

            # 2. Get all verses shown today to avoid repeating recently shown verses
            cursor.execute("SELECT verse_id FROM active_queue WHERE day_date = ?", (today_str,))
            already_shown_today = [r["verse_id"] for r in cursor.fetchall()]
            shown_today_count = len(already_shown_today)
            already_shown_set = set(already_shown_today)

            # 3. Pull pool of candidate verses for active theme & translation
            candidates = []

            # Check if active theme is Custom
            is_custom = (settings.active_theme == ScriptureTheme.CUSTOM or str(settings.active_theme.value).lower() == "custom")
            if is_custom and settings.active_custom_theme_id:
                ct = self.get_custom_theme(settings.active_custom_theme_id)
                if ct:
                    # A. Seed references (range-aware: 'John 10:11-15' expands to a passage)
                    if ct.seed_references:
                        for ref in ct.seed_references:
                            seed_verse = self.get_verse_by_ref(ref, settings.active_translation.value)
                            if seed_verse:
                                candidates.append(seed_verse)

                    # B. Dynamic vector search across ALL theme anchors, for a rich,
                    #    on-theme pool the delivery can rotate through with variety.
                    if ct.semantic_anchors:
                        from engine.theme_architect import theme_architect
                        for anchor in ct.semantic_anchors:
                            matches = theme_architect.vector_search_verses(
                                anchor,
                                translation=settings.active_translation.value,
                                top_k=12,
                                min_similarity=0.36
                            )
                            for v_id, score in matches:
                                if v_id not in [c.id for c in candidates]:
                                    v_match = self.get_verse_by_id(v_id)
                                    if v_match:
                                        candidates.append(v_match)

            if not candidates:
                theme_str = settings.active_theme.value if hasattr(settings.active_theme, 'value') else str(settings.active_theme)
                
                # Query precomputed semantic theme index
                cursor.execute("""
                    SELECT v.*, s.score
                    FROM theme_semantic_index s
                    JOIN verses v ON s.verse_id = v.id
                    WHERE s.theme = ? AND v.translation = ?
                    ORDER BY s.score DESC
                    LIMIT 200
                """, (theme_str, settings.active_translation.value))
                rows = cursor.fetchall()
                
                if rows:
                    candidates = [self._row_to_verse(r) for r in rows]
                else:
                    cursor.execute(
                        "SELECT * FROM verses WHERE (theme = ? OR tags LIKE ?) AND translation = ? ORDER BY id ASC LIMIT 50",
                        (theme_str, f"%{theme_str}%", settings.active_translation.value)
                    )
                    rows = cursor.fetchall()
                    candidates = [self._row_to_verse(r) for r in rows]

            if not candidates:
                return None

            # 3b. Collapse candidates to ONE representative per passage, normalised to
            #     the passage's start verse. Prevents the same passage (e.g. Proverbs
            #     1:1-6) from recurring via different anchor verses, and makes the
            #     same-day / cross-day de-dup below consistent.
            trans_val = settings.active_translation.value if hasattr(settings.active_translation, 'value') else str(settings.active_translation)
            seen_spans = set()
            deduped = []
            for v in candidates:
                start_v, end_v = self.get_passage_span(v.book, v.chapter, v.verse, trans_val)
                span_key = (v.book, v.chapter, start_v, end_v)
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)
                if start_v != v.verse:
                    rep = self.get_verse_by_ref(f"{v.book} {v.chapter}:{start_v}", trans_val) or v
                    deduped.append(rep)
                else:
                    deduped.append(v)
            candidates = deduped

            # 4. Filter out verses already shown today AND verses shown recently for
            #    THIS theme (cross-day memory), so every theme — preset or custom —
            #    rotates through its whole pool instead of replaying the same verses
            #    in the same order every day.
            if is_custom and settings.active_custom_theme_id:
                theme_key = f"custom:{settings.active_custom_theme_id}"
            else:
                theme_key = f"preset:{settings.active_theme.value if hasattr(settings.active_theme, 'value') else settings.active_theme}"

            cursor.execute("SELECT verse_id FROM theme_history WHERE theme_key = ?", (theme_key,))
            history_ids = {r["verse_id"] for r in cursor.fetchall()}

            unshown = [v for v in candidates if v.id not in already_shown_set and v.id not in history_ids]

            # Once a theme has cycled through its entire pool, reset its history so it
            # starts fresh rather than running dry.
            if not unshown:
                cursor.execute("DELETE FROM theme_history WHERE theme_key = ?", (theme_key,))
                history_ids = set()
                unshown = [v for v in candidates if v.id not in already_shown_set]

            # Optional: Sub-topic biasing if personal_context provided
            has_personal_ctx = bool(settings.personal_context and settings.personal_context.strip())
            if unshown and has_personal_ctx:
                try:
                    from engine.bedrock_engine import bedrock_engine
                    import numpy as np
                    ctx_vec = bedrock_engine.generate_embedding(settings.personal_context.strip())
                    if ctx_vec is not None:
                        # Rank unshown candidates by context alignment
                        q_norm = ctx_vec / max(1e-10, np.linalg.norm(ctx_vec))
                        unshown_scores = []
                        for v in unshown[:30]:
                            cursor.execute("SELECT embedding_blob FROM verses WHERE id = ?", (v.id,))
                            erow = cursor.fetchone()
                            if erow and erow["embedding_blob"]:
                                vec = np.frombuffer(erow["embedding_blob"], dtype=np.float32)
                                v_norm = vec / max(1e-10, np.linalg.norm(vec))
                                sim = float(np.dot(v_norm, q_norm))
                                unshown_scores.append((v, sim))
                            else:
                                unshown_scores.append((v, 0.0))
                        unshown_scores.sort(key=lambda x: x[1], reverse=True)
                        unshown = [x[0] for x in unshown_scores]
                except Exception:
                    pass

            import random
            if unshown:
                # Draw with variety from the whole on-theme pool so it flows and never
                # feels hardcoded. When the user gave a personal context we instead keep
                # the context-ranked order (best-aligned verse first).
                if has_personal_ctx:
                    chosen_verse = unshown[0]
                else:
                    chosen_verse = random.choice(unshown)
            else:
                last_shown_id = already_shown_today[-1] if already_shown_today else None
                fallback_pool = [v for v in candidates if v.id != last_shown_id] or candidates
                chosen_verse = random.choice(fallback_pool)

            # Remember this pick for the theme (cross-day rotation memory, all themes).
            if chosen_verse and chosen_verse.id:
                cursor.execute(
                    "INSERT INTO theme_history (theme_key, verse_id) VALUES (?, ?) "
                    "ON CONFLICT(theme_key, verse_id) DO UPDATE SET shown_at = CURRENT_TIMESTAMP",
                    (theme_key, chosen_verse.id)
                )

            # 5. Insert into active_queue and mark shown
            cursor.execute("""
                INSERT INTO active_queue (day_date, verse_id, sequence_order, is_shown, shown_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            """, (today_str, chosen_verse.id, shown_today_count + 1))
            conn.commit()

            return self.expand_to_passage(chosen_verse)

    def _row_to_verse(self, row: sqlite3.Row) -> VerseModel:
        tags_raw = row["tags"] if "tags" in row.keys() else "[]"
        tags = json.loads(tags_raw) if tags_raw else []
        return VerseModel(
            id=row["id"],
            book=row["book"],
            chapter=row["chapter"],
            verse=row["verse"],
            reference=row["reference"],
            translation=BibleTranslation(row["translation"]),
            text=row["text"],
            theme=ScriptureTheme(row["theme"]) if row["theme"] in [t.value for t in ScriptureTheme] else ScriptureTheme.FAITH,
            surrounding_context=row["surrounding_context"],
            key_original_words=row["key_original_words"],
            tags=tags,
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row.keys() and row["created_at"] else None
        )
    def get_next_verse_for_user(self, theme=None, translation=None) -> Optional[Dict]:
        """
        Gets the next verse for the user as a simple dict, suitable for the popup card.
        Wraps get_next_queue_verse() and converts VerseModel -> dict.
        """
        verse = self.get_next_queue_verse()
        if verse:
            settings = self.get_user_settings()
            is_custom = (settings.active_theme == ScriptureTheme.CUSTOM or str(settings.active_theme.value).lower() == "custom")
            if is_custom and settings.active_custom_theme_title:
                active_theme_label = settings.active_custom_theme_title
            else:
                active_theme_label = settings.active_theme.value if hasattr(settings.active_theme, 'value') else str(settings.active_theme)

            return {
                "id": verse.id,
                "reference": verse.reference,
                "translation": verse.translation.value if hasattr(verse.translation, 'value') else str(verse.translation),
                "text": verse.text,
                "theme": active_theme_label,
                "book": verse.book,
                "chapter": verse.chapter,
                "verse": verse.verse,
            }
        return None


# Global Database Instance
db = DatabaseManager()
