"""
Scriptaz AI Custom Theme Architect & Theological Normalizer
Bridges natural language life situations into structured biblical themes,
generates semantic search anchors, and queries the local SQLite vector database (Titan V2).
"""

import sys
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config
from core.models import CustomThemeModel, VerseModel, BibleTranslation, ScriptureTheme
from core.db import db
from engine.bedrock_engine import bedrock_engine

logger = logging.getLogger("scriptaz.theme_architect")


SYSTEM_PROMPT = """You are a seasoned biblical scholar and empathetic pastoral counselor.
Your mission is to bridge modern human workplace, emotional, and personal life struggles to sound, Christ-centered scripture.

Given a user's situation or focus:
1. Generate an inspiring, dignified 3 to 6 word "theme_title".
2. Write a 1-sentence "theological_summary" summarizing God's perspective on this situation.
3. Formulate 4 to 6 "semantic_anchors" (theological phrases optimized for semantic vector search across Bible translations).
4. Provide 3 to 5 exact "seed_references" (e.g. "Philippians 4:6-7", "Proverbs 15:1", "James 1:5", "Psalm 23:1-3").

Return ONLY valid JSON matching this exact structure with no markdown wrapper or extra text:
{
  "theme_title": "Wisdom & Peace in Workplace Conflict",
  "theological_summary": "God grants discernment in disagreement, commanding gentle speech and trust in divine sovereignty.",
  "semantic_anchors": [
    "wisdom that is peaceable gentle and willing to yield",
    "soft answer turns away wrath and prevents strife",
    "peace of God guarding the heart and mind to give sleep",
    "trusting the Lord to direct the steps of leadership"
  ],
  "seed_references": [
    "James 3:17-18",
    "Proverbs 15:1",
    "Psalm 4:8",
    "Proverbs 3:5-6"
  ]
}"""


class ThemeArchitect:
    """Orchestrates AI Theological Normalization and Local Vector Retrieval for Custom Themes."""

    def __init__(self):
        self.bedrock = bedrock_engine
        self._cached_trans = None
        self._cached_ids = None
        self._cached_matrix = None

    def normalize_theme_prompt(self, user_prompt: str) -> Dict[str, Any]:
        """Calls Bedrock (DeepSeek-R1 / Nova-Lite) to normalize a user prompt into structured biblical anchors."""
        if not user_prompt or not user_prompt.strip():
            return {
                "theme_title": "Personal Devotion & Peace",
                "theological_summary": "Drawing near to God in quiet contemplation and steadfast prayer.",
                "semantic_anchors": ["peace of God", "trusting in the Lord with all your heart", "God as our refuge and strength"],
                "seed_references": ["Philippians 4:6-7", "Proverbs 3:5-6", "Psalm 46:1-3"]
            }

        prompt = f"User situation / focus:\n\"{user_prompt.strip()}\"\n\nGenerate the structured JSON biblical theme blueprint."
        
        try:
            raw_response = self.bedrock.generate_text(prompt=prompt, system_prompt=SYSTEM_PROMPT, max_tokens=1500)
            text = raw_response.strip()

            # 1. Strip DeepSeek-R1 reasoning think tags if present
            if "<think>" in text and "</think>" in text:
                text = text.split("</think>", 1)[-1].strip()

            # 2. Extract markdown code block if present
            if "```json" in text:
                text = text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in text:
                text = text.split("```", 1)[1].split("```", 1)[0].strip()

            # 3. Find JSON bracket boundaries
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx + 1]

            data = json.loads(text.strip())
            
            # Ensure mandatory fields are present and dignified
            if not data.get("theme_title") or len(data["theme_title"].strip()) < 3:
                data["theme_title"] = "Biblical Focus: " + user_prompt.strip()[:30].title()
            if not data.get("theological_summary"):
                data["theological_summary"] = f"God's sovereign wisdom and peace for {user_prompt.strip()}."
            if not data.get("semantic_anchors"):
                data["semantic_anchors"] = ["peace of God", "trusting the Lord", "strength and courage"]
            if not data.get("seed_references"):
                data["seed_references"] = ["Philippians 4:6-7", "Proverbs 3:5-6", "Joshua 1:9"]

            return data
        except Exception as e:
            logger.warning(f"AI normalizer fallback triggered: {e}")
            
            # Intelligent offline theological normalization
            words = [w.strip() for w in user_prompt.strip().split() if len(w.strip()) > 3][:4]
            title_core = " & ".join(words).title() if words else "Workday Guidance"
            dignified_title = f"Steadfast Faith: {title_core}"
            
            return {
                "theme_title": dignified_title,
                "theological_summary": f"Standing firm in God's promises and wisdom when facing {user_prompt.strip()}.",
                "semantic_anchors": [
                    "peace of God guarding the heart",
                    "trusting in the Lord with all your heart",
                    "God is our refuge and strength very present help",
                    user_prompt.strip()
                ],
                "seed_references": ["Philippians 4:6-7", "Proverbs 3:5-6", "Psalm 46:1", "Isaiah 41:10"]
            }

    def _ensure_vector_cache(self, translation: str):
        """Loads and normalizes all 31,102 vectors for the given translation in memory."""
        if self._cached_trans == translation and self._cached_matrix is not None:
            return

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, embedding_blob FROM verses WHERE translation = ? AND embedding_blob IS NOT NULL",
                (translation,)
            )
            rows = cursor.fetchall()

        if not rows:
            return

        self._cached_ids = [r["id"] for r in rows]
        matrix = np.vstack([np.frombuffer(r["embedding_blob"], dtype=np.float32) for r in rows])
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0] = 1e-10
        self._cached_matrix = matrix / norms[:, None]
        self._cached_trans = translation

    def vector_search_verses(
        self,
        query_text: str,
        translation: str = "NKJV",
        top_k: int = 20,
        min_similarity: float = 0.38
    ) -> List[Tuple[int, float]]:
        """
        Embeds query_text with Titan V2 and performs cosine similarity search
        against SQLite's precomputed embeddings in <15ms.
        """
        query_vec = self.bedrock.generate_embedding(query_text)
        if query_vec is None:
            return []

        self._ensure_vector_cache(translation)
        if self._cached_matrix is None or not self._cached_ids:
            return []

        q_norm = query_vec / max(1e-10, np.linalg.norm(query_vec))
        similarities = np.dot(self._cached_matrix, q_norm)

        ranked_indices = np.argsort(similarities)[::-1]
        results = []
        for idx in ranked_indices[:top_k]:
            sim = float(similarities[idx])
            if sim >= min_similarity:
                results.append((self._cached_ids[idx], sim))

        return results

    def curate_custom_theme(
        self,
        user_prompt: str,
        preferred_translation: str = "NKJV"
    ) -> CustomThemeModel:
        """
        End-to-end pipeline:
        1. Normalizes user prompt via AI.
        2. Vector searches local SQLite embeddings across all anchors.
        3. Saves and activates the custom theme in SQLite.
        """
        norm_data = self.normalize_theme_prompt(user_prompt)
        title = norm_data.get("theme_title", "Custom Theme")
        summary = norm_data.get("theological_summary", "")
        anchors = norm_data.get("semantic_anchors", [])
        seeds = norm_data.get("seed_references", [])

        # Save to SQLite
        theme_id = db.save_custom_theme(
            title=title,
            user_prompt=user_prompt,
            theological_summary=summary,
            semantic_anchors=anchors,
            seed_references=seeds,
            is_active=True
        )

        return CustomThemeModel(
            id=theme_id,
            title=title,
            user_prompt=user_prompt,
            theological_summary=summary,
            semantic_anchors=anchors,
            seed_references=seeds,
            is_active=True
        )

    def get_next_custom_theme_verse(
        self,
        theme: CustomThemeModel,
        translation: str = "NKJV"
    ) -> Optional[VerseModel]:
        """
        Retrieves the next unshown scripture from the custom theme's dynamic vector stream.
        """
        shown_ids = db.get_custom_theme_shown_verse_ids(theme.id) if theme.id else set()

        # 1. First, check any seed references not yet shown
        for ref in theme.seed_references:
            v = db.get_verse_by_ref(ref, translation)
            if v and v.id and v.id not in shown_ids:
                if theme.id:
                    db.record_custom_theme_shown(theme.id, v.id)
                v.theme = ScriptureTheme.CUSTOM
                return v

        # 2. Dynamic multi-anchor vector search
        candidate_ids = []
        for anchor in theme.semantic_anchors:
            matches = self.vector_search_verses(anchor, translation=translation, top_k=10, min_similarity=0.45)
            for v_id, score in matches:
                if v_id not in shown_ids and v_id not in candidate_ids:
                    candidate_ids.append(v_id)

        # 3. Pull first unshown candidate
        if candidate_ids:
            next_id = candidate_ids[0]
            v = db.get_verse_by_id(next_id)
            if v:
                if theme.id:
                    db.record_custom_theme_shown(theme.id, v.id)
                v.theme = ScriptureTheme.CUSTOM
                return v

        # 4. Fallback if all candidates have been shown: reset history or pick top matching
        if theme.semantic_anchors:
            matches = self.vector_search_verses(theme.semantic_anchors[0], translation=translation, top_k=5)
            if matches:
                v = db.get_verse_by_id(matches[0][0])
                if v:
                    v.theme = ScriptureTheme.CUSTOM
                    return v

        return None


# Global Theme Architect Instance
theme_architect = ThemeArchitect()
