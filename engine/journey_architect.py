"""
Scriptaz Journey Architect
==========================
Builds a one-time, ordered TEACHING ARC for a theme so the user is taken on a
journey of understanding — from first recognizing the situation, to God's
perspective on it, to living it out — instead of receiving disconnected verses.

Design (mirrors the passage builder's philosophy):
  * The intelligence runs ONCE, at theme-creation time (custom) or once globally
    (presets) — never at delivery. Delivery just walks the stored stages.
  * The model only ARRANGES a pool of real, already-verified verses. It cannot
    invent references (every stage is validated against the pool it was given),
    which also removes the old "AI-invented seed reference doesn't exist" bug.
  * Uses the cheap/fast fallback model (Nova Lite) via forced tool output.
"""

import logging
import time
from typing import List, Dict, Any, Tuple

from core.db import db
from core.models import CustomThemeModel, UserSettingsModel, ScriptureTheme, BibleTranslation
from engine.bedrock_engine import bedrock_engine

logger = logging.getLogger("scriptaz.journey_architect")

# Canonical translation used to BUILD the pool text/references. References are
# canonical (Book chap:verse) so they resolve against any translation at delivery.
POOL_TRANSLATION = "NKJV"
POOL_CAP = 40          # max verses handed to one arrange call (context guard, not an arc cap)
MIN_STAGES = 2         # fewer than this isn't a journey — fall back to ambient rotation

JOURNEY_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "stages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "reference": {"type": "string"},
                    "phase_title": {"type": "string"},
                    "insight": {"type": "string"},
                },
                "required": ["reference", "phase_title", "insight"],
            },
        }
    },
    "required": ["stages"],
}

SYSTEM_PROMPT = (
    "You are arranging a teaching journey for someone exploring the biblical theme "
    "'{theme_title}' — described as: {theological_summary}. Below is a pool of real, "
    "verified verses/passages already matched to this theme. Every verse has already "
    "been judged relevant — include ALL of them, drop none, and add none that is not "
    "listed. Your job is to ARRANGE them so the reader is carried on a journey of "
    "understanding: from first recognizing the situation, to grasping God's perspective, "
    "to living it out.\n\n"
    "Return an ordered list of stages — one entry per verse, in the exact order the "
    "reader should receive them. Group the verses into a small number of DISTINCT phases "
    "(typically 4 to 8), each a real step in the progression: give every verse in the "
    "same phase the same short 'phase_title' (2-4 words), and keep verses of one phase "
    "consecutive before moving to the next phase. For EACH verse write one sentence of "
    "'insight' SPECIFIC to that verse — what it uniquely adds at this point. Do not reuse "
    "the same insight sentence for multiple verses; each verse earns its own reason. "
    "Call build_journey with your result."
)


class JourneyArchitect:
    # ------------------------------------------------------------------
    # Pool construction
    # ------------------------------------------------------------------
    def _passage_reference_for(self, verse, translation: str) -> Tuple[str, str]:
        """Returns (canonical_reference, joined_text) for the passage containing verse."""
        start_v, end_v = db.get_passage_span(verse.book, verse.chapter, verse.verse, translation)
        if end_v > start_v:
            ref = f"{verse.book} {verse.chapter}:{start_v}-{end_v}"
        else:
            ref = f"{verse.book} {verse.chapter}:{start_v}"
        pieces = db.get_passage_pieces(ref, translation)
        text = " ".join(t for _, t in pieces) if pieces else verse.text
        return ref, text

    def _pool_from_custom(self, theme: CustomThemeModel) -> List[Dict[str, str]]:
        from engine.theme_architect import theme_architect
        seen_refs = set()
        pool: List[Dict[str, str]] = []

        def add(verse, score):
            if not verse:
                return
            ref, text = self._passage_reference_for(verse, POOL_TRANSLATION)
            if ref in seen_refs:
                return
            seen_refs.add(ref)
            pool.append({"reference": ref, "text": text, "score": score})

        # Seeds first (highest intent), then vector matches across all anchors.
        for ref in (theme.seed_references or []):
            add(db.get_verse_by_ref(ref, POOL_TRANSLATION), 1.0)
        for anchor in (theme.semantic_anchors or []):
            for v_id, score in theme_architect.vector_search_verses(
                anchor, translation=POOL_TRANSLATION, top_k=12, min_similarity=0.36
            ):
                add(db.get_verse_by_id(v_id), score)

        pool.sort(key=lambda x: x["score"], reverse=True)
        return pool[:POOL_CAP]

    def _pool_from_preset(self, theme_name: str) -> List[Dict[str, str]]:
        seen_refs = set()
        pool: List[Dict[str, str]] = []
        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT v.*, s.score FROM theme_semantic_index s
                JOIN verses v ON s.verse_id = v.id
                WHERE s.theme = ? AND v.translation = ?
                ORDER BY s.score DESC LIMIT 120
            """, (theme_name, POOL_TRANSLATION))
            rows = cur.fetchall()
        for r in rows:
            verse = db._row_to_verse(r)
            ref, text = self._passage_reference_for(verse, POOL_TRANSLATION)
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            pool.append({"reference": ref, "text": text, "score": r["score"]})
        return pool[:POOL_CAP]

    # ------------------------------------------------------------------
    # Arrange + validate
    # ------------------------------------------------------------------
    def _arrange(self, title: str, summary: str, pool: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if len(pool) < MIN_STAGES:
            return []

        lines = "\n".join(
            f'- {p["reference"]} — "{p["text"][:160]}"' for p in pool
        )
        user_text = f"Theme: {title}\nSummary: {summary}\n\nVerified verse pool:\n{lines}"
        system = SYSTEM_PROMPT.format(theme_title=title, theological_summary=summary or title)

        result = None
        for attempt in range(3):
            result = bedrock_engine.converse_tool(
                user_text=user_text,
                tool_name="build_journey",
                tool_schema=JOURNEY_TOOL_SCHEMA,
                system_prompt=system,
                tool_description="Arrange the verse pool into an ordered teaching journey.",
                max_tokens=4000,
                temperature=0.2,
            )
            if result and "stages" in result:
                break
            time.sleep(0.8 * (attempt + 1))  # transient model/throttle backoff
        if not result or "stages" not in result:
            return []

        pool_refs = {p["reference"] for p in pool}
        # Case-insensitive / whitespace-tolerant lookup back to the canonical ref.
        norm = {self._norm(p["reference"]): p["reference"] for p in pool}

        ordered: List[Dict[str, str]] = []
        used_refs = set()
        for item in result["stages"]:
            ref = (item.get("reference") or "").strip()
            title_s = (item.get("phase_title") or "").strip()
            insight = (item.get("insight") or "").strip()
            canon_ref = ref if ref in pool_refs else norm.get(self._norm(ref))
            if not canon_ref:
                logger.warning(f"Journey stage referenced '{ref}' not in pool — dropped.")
                continue
            if canon_ref in used_refs:
                continue  # model duplicated a reference
            used_refs.add(canon_ref)
            ordered.append({"reference": canon_ref, "stage_title": title_s, "rationale": insight})

        # "Don't omit" check — log any pool verse the model left out (not fatal).
        omitted = pool_refs - used_refs
        if omitted:
            logger.warning(f"Journey omitted {len(omitted)} pool refs despite instruction: {sorted(omitted)[:8]}")

        return ordered if len(ordered) >= MIN_STAGES else []

    @staticmethod
    def _norm(ref: str) -> str:
        return "".join(ref.lower().split())

    # ------------------------------------------------------------------
    # Public builders
    # ------------------------------------------------------------------
    def build_journey_for_custom_theme(self, theme: CustomThemeModel) -> int:
        """Builds + stores the arc for a custom theme. Returns stage count (0 = none)."""
        if not theme or not theme.id:
            return 0
        pool = self._pool_from_custom(theme)
        stages = self._arrange(theme.title, theme.theological_summary or "", pool)
        theme_key = f"custom:{theme.id}"
        if stages:
            db.save_journey_stages(theme_key, stages)
            logger.info(f"Journey built for {theme_key}: {len(stages)} stages from pool of {len(pool)}.")
        else:
            db.clear_journey(theme_key)
            logger.warning(f"No journey built for {theme_key} — delivery will use ambient rotation.")
        return len(stages)

    def build_journey_for_preset(self, theme_name: str) -> int:
        """Builds + stores the arc for a preset theme (run once, shared by all users)."""
        pool = self._pool_from_preset(theme_name)
        summary = f"God's heart and wisdom on {theme_name.lower()} for daily life."
        stages = self._arrange(theme_name, summary, pool)
        theme_key = f"preset:{theme_name}"
        if stages:
            db.save_journey_stages(theme_key, stages)
            logger.info(f"Journey built for {theme_key}: {len(stages)} stages from pool of {len(pool)}.")
        else:
            db.clear_journey(theme_key)
            logger.warning(f"No journey built for {theme_key}.")
        return len(stages)


journey_architect = JourneyArchitect()
