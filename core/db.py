"""
Scriptaz SQLite Database Engine
Provides thread-safe local data storage, multi-translation verse queries,
$0-cost Deep Insight caching, Strong's lexicon lookups, and active-time workday queues.
"""

import sqlite3
import hashlib
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from core.config import config
from core.models import (
    VerseModel,
    BibleTranslation,
    ScriptureTheme,
    UserSettingsModel,
    StructuredInsight,
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

            # 2. Deep Insight Cache Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS insights_cache (
                    cache_key TEXT PRIMARY KEY,
                    verse_ref TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    theme TEXT NOT NULL,
                    personal_context TEXT,
                    raw_output TEXT NOT NULL,
                    context_setting TEXT NOT NULL,
                    word_illumination TEXT NOT NULL,
                    christ_revelation TEXT NOT NULL,
                    connected_scriptures TEXT,
                    model_used TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_ref ON insights_cache(verse_ref, theme);")

            # 3. User Settings Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

            # 4. Pinned Verses Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pinned_verses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    verse_id INTEGER NOT NULL,
                    notes TEXT,
                    pinned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (verse_id) REFERENCES verses(id) ON DELETE CASCADE,
                    UNIQUE(verse_id)
                );
            """)

            # 5. Active Workday Queue Table
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

            conn.commit()

    @staticmethod
    def generate_cache_key(reference: str, translation: str, theme: str, personal_context: Optional[str]) -> str:
        clean_context = (personal_context or "").strip().lower()
        key_input = f"{reference.strip().lower()}:{translation.strip().upper()}:{theme.strip().lower()}:{clean_context}"
        return hashlib.sha256(key_input.encode("utf-8")).hexdigest()

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

    def get_verse_by_ref(self, reference: str, translation: str = "KJV") -> Optional[VerseModel]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM verses WHERE reference = ? AND translation = ?", (reference, translation))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_verse(row)

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

    def get_all_translations_for_ref(self, reference: str) -> Dict[str, str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT translation, text FROM verses WHERE reference = ?", (reference,))
            rows = cursor.fetchall()
            return {r["translation"]: r["text"] for r in rows}

    def count_verses(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM verses")
            return cursor.fetchone()["count"]

    def get_cached_insight(self, cache_key: str) -> Optional[StructuredInsight]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM insights_cache WHERE cache_key = ?", (cache_key,))
            row = cursor.fetchone()
            if not row:
                return None
            
            connected_scripts = json.loads(row["connected_scriptures"]) if row["connected_scriptures"] else []
            return StructuredInsight(
                context_and_setting=row["context_setting"],
                original_word_illumination=row["word_illumination"],
                christ_centered_revelation=row["christ_revelation"],
                connected_scriptures=connected_scripts,
                is_cached=True,
                model_used=row["model_used"],
                cached_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            )

    def save_cached_insight(
        self,
        cache_key: str,
        verse_ref: str,
        translation: str,
        theme: str,
        personal_context: Optional[str],
        raw_output: str,
        insight: StructuredInsight,
        model_used: str
    ):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO insights_cache (
                    cache_key, verse_ref, translation, theme, personal_context,
                    raw_output, context_setting, word_illumination, christ_revelation,
                    connected_scriptures, model_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    raw_output = excluded.raw_output,
                    context_setting = excluded.context_setting,
                    word_illumination = excluded.word_illumination,
                    christ_revelation = excluded.christ_revelation,
                    connected_scriptures = excluded.connected_scriptures,
                    model_used = excluded.model_used
            """, (
                cache_key,
                verse_ref,
                translation,
                theme,
                personal_context or "",
                raw_output,
                insight.context_and_setting,
                insight.original_word_illumination,
                insight.christ_centered_revelation,
                json.dumps(insight.connected_scriptures),
                model_used
            ))
            conn.commit()

    def get_settings(self) -> UserSettingsModel:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_settings")
            rows = dict(cursor.fetchall())
            
            return UserSettingsModel(
                user_name=rows.get("user_name", "Avidan"),
                interval_minutes=int(rows.get("interval_minutes", config.default_interval_minutes)),
                daily_limit=int(rows.get("daily_limit", config.default_daily_limit)),
                active_translation=BibleTranslation(rows.get("active_translation", config.default_bible_version)),
                active_theme=ScriptureTheme(rows.get("active_theme", config.default_theme)),
                personal_context=rows.get("personal_context", ""),
                launch_on_startup=rows.get("launch_on_startup", "false").lower() == "true",
                dark_mode=rows.get("dark_mode", "true").lower() == "true"
            )

    def update_settings(self, settings: UserSettingsModel):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            settings_dict = {
                "user_name": settings.user_name,
                "interval_minutes": str(settings.interval_minutes),
                "daily_limit": str(settings.daily_limit),
                "active_translation": settings.active_translation.value if hasattr(settings.active_translation, 'value') else str(settings.active_translation),
                "active_theme": settings.active_theme.value if hasattr(settings.active_theme, 'value') else str(settings.active_theme),
                "personal_context": settings.personal_context,
                "launch_on_startup": str(settings.launch_on_startup).lower(),
                "dark_mode": str(settings.dark_mode).lower()
            }
            for k, v in settings_dict.items():
                cursor.execute(
                    "INSERT INTO user_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (k, v)
                )
            conn.commit()

    def pin_verse(self, verse_id: int, notes: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pinned_verses (verse_id, notes) VALUES (?, ?)
                ON CONFLICT(verse_id) DO UPDATE SET notes = excluded.notes
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

    def get_pinned_verses(self) -> List[PinnedVerseModel]:
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
            for r in rows:
                result.append(PinnedVerseModel(
                    id=r["pin_id"],
                    verse_id=r["verse_id"],
                    reference=r["reference"],
                    translation=BibleTranslation(r["translation"]),
                    text=r["text"],
                    theme=ScriptureTheme(r["theme"]) if r["theme"] in [t.value for t in ScriptureTheme] else ScriptureTheme.SIN_AND_GRACE,
                    pinned_at=datetime.fromisoformat(r["pinned_at"]) if r["pinned_at"] else datetime.now(),
                    notes=r["notes"]
                ))
            return result

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
                return self._row_to_verse(row)

            cursor.execute("SELECT COUNT(*) as count FROM active_queue WHERE day_date = ?", (today_str,))
            shown_today_count = cursor.fetchone()["count"]

            if shown_today_count >= settings.daily_limit:
                pinned = self.get_pinned_verses()
                if pinned:
                    first_pinned = self.get_verse_by_id(pinned[0].verse_id)
                    if first_pinned:
                        return first_pinned
                return None

            verses = self.get_verses_by_theme(settings.active_theme.value, settings.active_translation.value)
            if not verses:
                cursor.execute("SELECT * FROM verses WHERE translation = ? LIMIT 10", (settings.active_translation.value,))
                rows = cursor.fetchall()
                verses = [self._row_to_verse(r) for r in rows]
                if not verses:
                    return None

            cursor.execute("SELECT verse_id FROM active_queue WHERE day_date = ?", (today_str,))
            already_queued_ids = {r["verse_id"] for r in cursor.fetchall()}

            for idx, verse in enumerate(verses):
                if verse.id not in already_queued_ids:
                    cursor.execute("""
                        INSERT INTO active_queue (day_date, verse_id, sequence_order, is_shown, shown_at)
                        VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                    """, (today_str, verse.id, shown_today_count + 1))
                    conn.commit()
                    return verse

            cursor.execute("""
                INSERT INTO active_queue (day_date, verse_id, sequence_order, is_shown, shown_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            """, (today_str, verses[0].id, shown_today_count + 1))
            conn.commit()
            return verses[0]

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
            theme=ScriptureTheme(row["theme"]) if row["theme"] in [t.value for t in ScriptureTheme] else ScriptureTheme.SIN_AND_GRACE,
            surrounding_context=row["surrounding_context"],
            key_original_words=row["key_original_words"],
            tags=tags,
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row.keys() and row["created_at"] else None
        )


# Global Database Instance
db = DatabaseManager()
