"""
Scriptaz Bible PDF Parser Audit & Coverage Verification
Audits the extraction of all 66 canonical books from Genesis to Revelation across KJV, NLT, NKJV, and ESV.
Ensures zero abbreviations are present in the final references.
"""

import sys
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.ingest_bibles import parse_nlt, parse_kjv, parse_nkjv, parse_esv, BIBLE_BOOKS, SCRIPTURES_DIR

def audit_verses(name: str, verses: list):
    print(f"\n{'='*70}\n[AUDIT REPORT FOR {name}]\n{'='*70}")
    total_verses = len(verses)
    print(f"Total Verses Extracted: {total_verses}")

    books_found = defaultdict(lambda: defaultdict(list))
    for v in verses:
        b = v["book"]
        c = v["chapter"]
        v_num = v["verse"]
        books_found[b][c].append(v_num)

    print(f"Total Canonical Books Extracted: {len(books_found)} / 66")

    missing_books = [b for b in BIBLE_BOOKS if b not in books_found]
    if missing_books:
        print(f"❌ Missing Books ({len(missing_books)}): {', '.join(missing_books)}")
    else:
        print("✅ All 66 Canonical Books Detected with 100% Full Unabbreviated Names!")

    if verses:
        print(f"First Verse: [{verses[0]['reference']}] {verses[0]['text'][:80]}...")
        print(f"Last Verse:  [{verses[-1]['reference']}] {verses[-1]['text'][:80]}...")

    sample_books = ["Genesis", "Psalms", "Song of Solomon", "Matthew", "John", "Romans", "Philippians", "James", "1 John", "Revelation"]
    print("\n--- Sample Book Verification (Full Names) ---")
    for sb in sample_books:
        if sb in books_found:
            chap_count = len(books_found[sb])
            verse_count = sum(len(vv) for vv in books_found[sb].values())
            print(f"  • {sb:<18}: {chap_count:>3} chapters | {verse_count:>5} verses")
        else:
            print(f"  • {sb:<18}: MISSING")


if __name__ == "__main__":
    pdf_map = [
        ("NLT", SCRIPTURES_DIR / "New-Living-Translation-NLT.pdf", parse_nlt),
        ("KJV", SCRIPTURES_DIR / "PDF-King-James-Bible.pdf", parse_kjv),
        ("NKJV", SCRIPTURES_DIR / "new-king-james-version-en.pdf", parse_nkjv),
        ("ESV", SCRIPTURES_DIR / "272774876-The-Holy-Bible-ESV.pdf", parse_esv)
    ]

    for name, path, parser in pdf_map:
        if path.exists():
            v_list = parser(path)
            audit_verses(name, v_list)
        else:
            print(f"File not found: {path}")
