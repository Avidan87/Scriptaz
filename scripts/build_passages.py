"""
Scriptaz — One-Time Passage Segmentation Builder
=================================================
Computes, ONCE and offline, the natural passage unit each verse belongs to, so the
app can intelligently decide when a verse must be shown together with its connected
neighbours (e.g. Ephesians 1:17-19) versus standing alone (e.g. Proverbs 15:1).

The intelligence is grammar-driven — meaning, not mere topic similarity, decides:
  1. Sentence continuity  — a verse that does not end in . ! ? (ends on a comma,
     dash, colon, or mid-clause) runs on into the next; a verse that STARTS lowercase
     depends on the previous. This is grammatical and translation-agnostic.
  2. Logical connectives  — a verse opening with a genuinely backward-referential
     word (Therefore / For / Because / So / Wherefore / Which / Thus / Since ...)
     depends on the prior verse for its sense. Weak narrative openers ("And", "But",
     "Now", "Then") are deliberately NOT treated as joins — they routinely begin
     standalone verses, and joining on them would over-merge the whole Bible.
  3. Genre priors         — wisdom books (Proverbs, Ecclesiastes) bias to singletons.

Grouping honours: TARGET_LEN verses, snap to a sentence boundary, never exceed HARD_CAP.
Results are written to the `verse_passage_map` table (translation, book, chapter, verse)
-> (start_verse, end_verse). Delivery then just looks up the span; $0 and instant.

Run:  python scripts/build_passages.py
"""

import sys
import re
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config  # noqa: E402
from core.db import db  # noqa: E402

# ----------------------------------------------------------------------
# Tuning knobs
# ----------------------------------------------------------------------
TARGET_LEN = 5          # preferred passage length for logical (non-forced) growth
HARD_CAP = 7            # never bundle more than this many verses onto one card
WISDOM_SINGLETON_BOOKS = {"Proverbs", "Ecclesiastes"}

# First words that are genuinely backward-referential: the verse does not make
# sense without the prior one. Deliberately EXCLUDES weak narrative openers
# (and, but, now, then, yet, nor) which routinely begin standalone verses.
DEPENDENT_OPENERS = {
    "therefore", "for", "because", "so", "wherefore", "which", "thus",
    "since", "hence", "whereby", "thereby", "thereof", "whereupon", "wherein",
}

# Characters that legitimately END a sentence (allowing trailing quotes/brackets).
_TRAILING_STRIP = ' \t"\'”’)]'


def ends_sentence(text: str) -> bool:
    """True if the verse text finishes a complete sentence."""
    t = (text or "").rstrip(_TRAILING_STRIP)
    return bool(t) and t[-1] in ".!?"


def starts_dependent(text: str) -> bool:
    """True if the verse opens in a way that leans on the previous verse."""
    t = (text or "").lstrip(' \t"\'“‘([')
    if not t:
        return False
    # A lowercase opening is a hard grammatical dependency (mid-sentence split).
    if t[0].islower():
        return True
    first_word = re.split(r"[\s,;:.]", t, 1)[0].lower()
    return first_word in DEPENDENT_OPENERS


def starts_lowercase(text: str) -> bool:
    t = (text or "").lstrip(' \t"\'“‘([')
    return bool(t) and t[0].islower()


def segment_chapter(verses, is_wisdom: bool):
    """
    verses:  ordered list of (verse_no, text)
    Returns: dict verse_no -> (start_verse, end_verse)
    """
    n = len(verses)
    nums = [v for v, _ in verses]
    texts = {v: t for v, t in verses}

    def forced_join(i_num, j_num) -> bool:
        # j continues i's sentence: i didn't close, or j opens mid-sentence.
        return (not ends_sentence(texts[i_num])) or starts_lowercase(texts[j_num])

    def logical_join(i_num, j_num) -> bool:
        # Two complete sentences where j leans on i for its meaning.
        if is_wisdom:
            return False
        return ends_sentence(texts[i_num]) and starts_dependent(texts[j_num])

    result = {}
    idx = 0
    while idx < n:
        start = nums[idx]
        end = start
        e_idx = idx
        while e_idx + 1 < n:
            cur, nxt = nums[e_idx], nums[e_idx + 1]
            length = (e_idx - idx) + 1  # verses currently in the passage
            if forced_join(cur, nxt):
                if length >= HARD_CAP:
                    break  # protect the card even mid-sentence (very rare)
                e_idx += 1
                end = nxt
                continue
            if logical_join(cur, nxt) and length < TARGET_LEN:
                e_idx += 1
                end = nxt
                continue
            break

        # Snap to a sentence boundary: don't end a passage mid-sentence unless a
        # single sentence itself overran the cap.
        if not ends_sentence(texts[end]):
            back = e_idx
            while back > idx and not ends_sentence(texts[nums[back]]):
                back -= 1
            if ends_sentence(texts[nums[back]]):
                e_idx = back
                end = nums[back]

        for k in range(idx, e_idx + 1):
            result[nums[k]] = (start, end)
        idx = e_idx + 1

    return result


def main():
    print(f"Building passage map -> {config.db_path}")
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verse_passage_map (
                translation TEXT NOT NULL,
                book        TEXT NOT NULL,
                chapter     INTEGER NOT NULL,
                verse       INTEGER NOT NULL,
                start_verse INTEGER NOT NULL,
                end_verse   INTEGER NOT NULL,
                PRIMARY KEY (translation, book, chapter, verse)
            );
        """)
        cur.execute("DELETE FROM verse_passage_map;")

        cur.execute("SELECT DISTINCT translation FROM verses ORDER BY translation;")
        translations = [r["translation"] for r in cur.fetchall()]

        total_rows = 0
        total_passages = 0
        multi_passages = 0
        for trans in translations:
            cur.execute("""
                SELECT book, chapter, verse, text
                FROM verses WHERE translation = ?
                ORDER BY book, chapter, verse
            """, (trans,))
            rows = cur.fetchall()

            chapters = defaultdict(list)
            for r in rows:
                chapters[(r["book"], r["chapter"])].append((r["verse"], r["text"]))

            batch = []
            for (book, chapter), vlist in chapters.items():
                vlist.sort(key=lambda x: x[0])
                is_wisdom = book in WISDOM_SINGLETON_BOOKS
                spans = segment_chapter(vlist, is_wisdom)
                seen_spans = set()
                for vnum, (s, e) in spans.items():
                    batch.append((trans, book, chapter, vnum, s, e))
                    if (s, e) not in seen_spans:
                        seen_spans.add((s, e))
                        total_passages += 1
                        if e > s:
                            multi_passages += 1

            cur.executemany("""
                INSERT INTO verse_passage_map
                    (translation, book, chapter, verse, start_verse, end_verse)
                VALUES (?, ?, ?, ?, ?, ?)
            """, batch)
            total_rows += len(batch)
            print(f"  {trans}: {len(batch):>6} verses mapped")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_passage_lookup
            ON verse_passage_map(translation, book, chapter, verse);
        """)
        conn.commit()

    pct = (multi_passages / total_passages * 100) if total_passages else 0
    print(f"\nDone. {total_rows} verses mapped into {total_passages} passages "
          f"({multi_passages} multi-verse, {pct:.1f}%).")


if __name__ == "__main__":
    main()
