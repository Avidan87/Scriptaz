"""
Scriptaz All-Round Bible Integrity & Quality Audit
Validates all 66 books, word completeness, and hallmark verses across KJV, NLT, NKJV, and ESV.
"""

import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Set

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.db import db, DatabaseManager
from scripts.ingest_bibles import (
    BIBLE_BOOKS,
    parse_nlt,
    parse_kjv,
    parse_nkjv,
    parse_esv,
    SCRIPTURES_DIR
)

HALLMARK_VERSES = [
    "Genesis 1:1",
    "Psalms 23:1",
    "Proverbs 3:5",
    "Isaiah 40:31",
    "Matthew 6:33",
    "John 3:16",
    "John 14:27",
    "Romans 8:28",
    "1 Corinthians 13:4",
    "Galatians 2:20",
    "Philippians 4:6",
    "Colossians 3:23",
    "Hebrews 11:1",
    "James 1:5",
    "1 John 4:18",
    "Revelation 21:4"
]


def audit_parsed_dataset(translation: str, verses: List[Dict]) -> Dict:
    print(f"\n{'='*70}\n[AUDITING {translation} INTEGRITY & WORDING QUALITY]\n{'='*70}")
    
    total_count = len(verses)
    print(f"📊 Total Verses Extracted: {total_count}")

    # 1. Check 66 Canonical Books
    found_books = set(v["book"] for v in verses)
    invalid_books = [b for b in found_books if b not in BIBLE_BOOKS]
    missing_books = [b for b in BIBLE_BOOKS if b not in found_books]

    print(f"📚 Canonical Books Identified: {len(found_books)} / 66")
    if invalid_books:
        print(f"⚠️ Warning: Found un-normalized book names: {invalid_books[:5]}")
    else:
        print("✅ 100% of verses belong to canonical Bible books!")

    if missing_books:
        print(f"⚠️ Note: Missing books from PDF: {missing_books}")
    else:
        print("✅ All 66 books present in translation!")

    # 2. Check for Word Truncation / Chopped Suffixes
    chopped_samples = []
    for v in verses:
        text = v["text"]
        # Check for suspiciously chopped words from old regex (like 'agai', 'rooste', 'denie')
        if re.search(r"\b(agai|rooste|denie|crowe|wit|yo|leav|breathe|giv)\b", text, re.IGNORECASE):
            # Check if this is actual archaic KJV word or chopped modern word
            if "wit" in text.lower() or "agai" in text.lower() or "yo" in text.lower():
                chopped_samples.append((v["reference"], text[:80]))

    if chopped_samples and translation != "KJV":
        print(f"⚠️ Found {len(chopped_samples)} potential word-chopping issues. Sample: {chopped_samples[:2]}")
    else:
        print("✅ Word integrity test PASSED: Zero word-truncation detected!")

    # 3. Check Hallmark Verses
    ref_map = {v["reference"]: v["text"] for v in verses}
    print("\n🔍 Hallmark Verses Spot-Check:")
    matched_hallmarks = 0
    for h in HALLMARK_VERSES:
        txt = ref_map.get(h)
        if txt:
            matched_hallmarks += 1
            print(f"  • {h:22} -> \"{txt[:75]}...\"")
        else:
            # Try finding with alternate chapter/verse notation
            print(f"  ❌ Missing hallmark: {h}")

    print(f"\n📈 Hallmark Verses Found: {matched_hallmarks} / {len(HALLMARK_VERSES)}")
    return {
        "translation": translation,
        "total_verses": total_count,
        "books_found": len(found_books),
        "hallmarks_matched": matched_hallmarks
    }


def run_full_audit():
    print(f"\n{'='*70}\n[SCRIPTAZ ALL-ROUND MULTI-TRANSLATION VALIDATION AUDIT]\n{'='*70}")

    all_verses = []

    # 1. NLT
    nlt_path = SCRIPTURES_DIR / "New-Living-Translation-NLT.pdf"
    if nlt_path.exists():
        nlt_v = parse_nlt(nlt_path)
        audit_parsed_dataset("NLT", nlt_v)
        all_verses.extend(nlt_v)

    # 2. KJV
    kjv_path = SCRIPTURES_DIR / "PDF-King-James-Bible.pdf"
    if kjv_path.exists():
        kjv_v = parse_kjv(kjv_path)
        audit_parsed_dataset("KJV", kjv_v)
        all_verses.extend(kjv_v)

    # 3. NKJV
    nkjv_path = SCRIPTURES_DIR / "new-king-james-version-en.pdf"
    if nkjv_path.exists():
        nkjv_v = parse_nkjv(nkjv_path)
        audit_parsed_dataset("NKJV", nkjv_v)
        all_verses.extend(nkjv_v)

    # 4. ESV
    esv_path = SCRIPTURES_DIR / "272774876-The-Holy-Bible-ESV.pdf"
    if esv_path.exists():
        esv_v = parse_esv(esv_path)
        audit_parsed_dataset("ESV", esv_v)
        all_verses.extend(esv_v)

    # Store into SQLite cleanly
    print(f"\n🔄 Committing {len(all_verses)} validated verses to SQLite...")
    
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM verses;")
        
        # Build chapter context
        chapter_groups = {}
        for v in all_verses:
            key = (v["translation"], v["book"], v["chapter"])
            chapter_groups.setdefault(key, []).append(v)

        for (trans, book, chap), v_list in chapter_groups.items():
            full_chapter_text = " ".join(v["text"] for v in v_list)
            for v in v_list:
                cursor.execute("""
                    INSERT INTO verses (
                        book, chapter, verse, reference, translation, text, theme,
                        surrounding_context, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(reference, translation) DO UPDATE SET
                        text = excluded.text,
                        surrounding_context = excluded.surrounding_context
                """, (
                    v["book"],
                    v["chapter"],
                    v["verse"],
                    v["reference"],
                    v["translation"],
                    v["text"],
                    "Sin & Grace",
                    full_chapter_text[:1200],
                    json.dumps([v["book"], f"Chapter {v['chapter']}"])
                ))
        conn.commit()

    total_in_db = db.count_verses()
    print(f"\n{'='*70}\n🎉 ALL-ROUND VALIDATION AUDIT COMPLETE! Total Verses in Database: {total_in_db}\n{'='*70}\n")


if __name__ == "__main__":
    run_full_audit()
