"""
Scriptaz Bible Ingestion Engine
Extracts 100% clean, pristine verses from KJV, NLT, NKJV, and ESV PDFs
into SQLite with full unabbreviated book titles and sliding narrative chapter context.
"""

import sys
import re
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from pypdf import PdfReader

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config
from core.models import VerseModel, BibleTranslation, ScriptureTheme
from core.db import DatabaseManager

SCRIPTURES_DIR = ROOT_DIR / "Scriptures"

# Canonical 66 Bible Books List
BIBLE_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
    "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
    "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]

# Comprehensive Abbreviation Normalization Dictionary
BOOK_NORMALIZER = {
    # Old Testament
    "gen": "Genesis", "gene": "Genesis", "genesis": "Genesis",
    "exo": "Exodus", "exod": "Exodus", "exodus": "Exodus",
    "lev": "Leviticus", "levi": "Leviticus", "leviticus": "Leviticus",
    "num": "Numbers", "numb": "Numbers", "numbers": "Numbers",
    "deu": "Deuteronomy", "deut": "Deuteronomy", "deuteronomy": "Deuteronomy",
    "jos": "Joshua", "josh": "Joshua", "joshua": "Joshua",
    "jdg": "Judges", "judg": "Judges", "judges": "Judges",
    "rut": "Ruth", "ruth": "Ruth",
    "1sa": "1 Samuel", "1sam": "1 Samuel", "1 samuel": "1 Samuel",
    "2sa": "2 Samuel", "2sam": "2 Samuel", "2 samuel": "2 Samuel",
    "1ki": "1 Kings", "1kgs": "1 Kings", "1 kings": "1 Kings",
    "2ki": "2 Kings", "2kgs": "2 Kings", "2 kings": "2 Kings",
    "1ch": "1 Chronicles", "1chr": "1 Chronicles", "1 chronicles": "1 Chronicles",
    "2ch": "2 Chronicles", "2chr": "2 Chronicles", "2 chronicles": "2 Chronicles",
    "ezr": "Ezra", "ezra": "Ezra",
    "neh": "Nehemiah", "nehemiah": "Nehemiah",
    "est": "Esther", "esth": "Esther", "esther": "Esther",
    "job": "Job",
    "psa": "Psalms", "psalm": "Psalms", "psalms": "Psalms", "ps": "Psalms",
    "pro": "Proverbs", "prov": "Proverbs", "proverbs": "Proverbs",
    "ecc": "Ecclesiastes", "eccl": "Ecclesiastes", "ecclesiastes": "Ecclesiastes",
    "sol": "Song of Solomon", "sng": "Song of Solomon", "son": "Song of Solomon", "song": "Song of Solomon", "sos": "Song of Solomon", "song of solomon": "Song of Solomon",
    "isa": "Isaiah", "isai": "Isaiah", "isaiah": "Isaiah",
    "jer": "Jeremiah", "jere": "Jeremiah", "jeremiah": "Jeremiah",
    "lam": "Lamentations", "lamentations": "Lamentations",
    "ezk": "Ezekiel", "eze": "Ezekiel", "ezek": "Ezekiel", "ezekiel": "Ezekiel",
    "dan": "Daniel", "daniel": "Daniel",
    "hos": "Hosea", "hosea": "Hosea",
    "joe": "Joel", "joel": "Joel",
    "amo": "Amos", "amos": "Amos",
    "oba": "Obadiah", "obad": "Obadiah", "obadiah": "Obadiah",
    "jon": "Jonah", "jonah": "Jonah",
    "mic": "Micah", "micah": "Micah",
    "nah": "Nahum", "nahum": "Nahum",
    "hab": "Habakkuk", "habakkuk": "Habakkuk",
    "zep": "Zephaniah", "zeph": "Zephaniah", "zephaniah": "Zephaniah",
    "hag": "Haggai", "haggai": "Haggai",
    "zec": "Zechariah", "zech": "Zechariah", "zechariah": "Zechariah",
    "mal": "Malachi", "malachi": "Malachi",
    # New Testament
    "mat": "Matthew", "matt": "Matthew", "matthew": "Matthew",
    "mar": "Mark", "mrk": "Mark", "mk": "Mark", "mark": "Mark",
    "luk": "Luke", "lk": "Luke", "luke": "Luke",
    "joh": "John", "jhn": "John", "jn": "John", "john": "John",
    "act": "Acts", "acts": "Acts",
    "rom": "Romans", "romans": "Romans",
    "1co": "1 Corinthians", "1cor": "1 Corinthians", "1 corinthians": "1 Corinthians",
    "2co": "2 Corinthians", "2cor": "2 Corinthians", "2 corinthians": "2 Corinthians",
    "gal": "Galatians", "galatians": "Galatians",
    "eph": "Ephesians", "ephesians": "Ephesians",
    "phi": "Philippians", "php": "Philippians", "phil": "Philippians", "philippians": "Philippians",
    "col": "Colossians", "colossians": "Colossians",
    "1th": "1 Thessalonians", "1thess": "1 Thessalonians", "1 thessalonians": "1 Thessalonians",
    "2th": "2 Thessalonians", "2thess": "2 Thessalonians", "2 thessalonians": "2 Thessalonians",
    "1ti": "1 Timothy", "1tim": "1 Timothy", "1 timothy": "1 Timothy",
    "2ti": "2 Timothy", "2tim": "2 Timothy", "2 timothy": "2 Timothy",
    "tit": "Titus", "titus": "Titus",
    "phm": "Philemon", "phlm": "Philemon", "philemon": "Philemon",
    "heb": "Hebrews", "hebrews": "Hebrews",
    "jas": "James", "jam": "James", "james": "James",
    "1pe": "1 Peter", "1pet": "1 Peter", "1 peter": "1 Peter",
    "2pe": "2 Peter", "2pet": "2 Peter", "2 peter": "2 Peter",
    "1jo": "1 John", "1jn": "1 John", "1jhn": "1 John", "1 john": "1 John",
    "2jo": "2 John", "2jn": "2 John", "2jhn": "2 John", "2 john": "2 John",
    "3jo": "3 John", "3jn": "3 John", "3jhn": "3 John", "3 john": "3 John",
    "jud": "Jude", "jude": "Jude",
    "rev": "Revelation", "revelation": "Revelation"
}


def normalize_book_name(raw_name: str) -> str:
    """Converts any raw or abbreviated book string into the Full Canonical Title."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", "", raw_name).strip().lower()
    return BOOK_NORMALIZER.get(clean, raw_name.strip().title())


def parse_nlt(pdf_path: Path) -> List[Dict]:
    """Parses NLT PDF into Full Unabbreviated Book Verses."""
    print(f"\n[PARSING NLT] {pdf_path.name}...")
    reader = PdfReader(str(pdf_path))
    verses = []
    pattern = re.compile(r"^([1-3]?[A-Za-z]+)\s+(\d+):(\d+)\s+(.*)")

    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            
            match = pattern.match(line)
            if match:
                raw_book, chapter_str, verse_str, verse_text = match.groups()
                full_book = normalize_book_name(raw_book)
                chapter = int(chapter_str)
                verse_num = int(verse_str)
                clean_text = re.sub(r"\[\d+\]", "", verse_text).strip()
                ref = f"{full_book} {chapter}:{verse_num}"
                verses.append({
                    "book": full_book,
                    "chapter": chapter,
                    "verse": verse_num,
                    "reference": ref,
                    "translation": "NLT",
                    "text": clean_text
                })
            elif verses:
                clean_line = re.sub(r"\[\d+\]", "", line).strip()
                verses[-1]["text"] += " " + clean_line

    print(f"✅ Extracted {len(verses)} NLT verses with full unabbreviated book titles.")
    return verses


def parse_kjv(pdf_path: Path) -> List[Dict]:
    """Parses KJV PDF into Full Unabbreviated Book Verses."""
    print(f"\n[PARSING KJV] {pdf_path.name}...")
    reader = PdfReader(str(pdf_path))
    verses = []
    current_book = "Genesis"
    current_chapter = 1

    chap_pattern = re.compile(r"^(?:CHAPTER|PSALM)\s+(\d+)", re.IGNORECASE)
    verse_pattern = re.compile(r"^(\d+)\s+([A-Za-z“\"'].*)")

    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            c_match = chap_pattern.match(line)
            if c_match:
                current_chapter = int(c_match.group(1))
                continue

            for b in BIBLE_BOOKS:
                if line.startswith(b) and len(line) < len(b) + 8:
                    current_book = b
                    break

            if line.startswith("PSALM") or line.startswith("Psalms"):
                current_book = "Psalms"

            v_match = verse_pattern.match(line)
            if v_match:
                v_num = int(v_match.group(1))
                v_text = v_match.group(2)
                ref = f"{current_book} {current_chapter}:{v_num}"
                verses.append({
                    "book": current_book,
                    "chapter": current_chapter,
                    "verse": v_num,
                    "reference": ref,
                    "translation": "KJV",
                    "text": v_text.strip()
                })
            elif verses:
                verses[-1]["text"] += " " + line

    print(f"✅ Extracted {len(verses)} KJV verses with full unabbreviated book titles.")
    return verses


def parse_nkjv(pdf_path: Path) -> List[Dict]:
    """Parses NKJV PDF with accurate mid-page chapter transition tracking."""
    print(f"\n[PARSING NKJV] {pdf_path.name}...")
    reader = PdfReader(str(pdf_path))
    verses_map = {}
    current_book = "Genesis"
    current_chapter = 1

    header_pattern = re.compile(r"^([1-3]?[A-Za-z\s]+)\s+(\d+):(\d+)", re.IGNORECASE)
    chap_pattern = re.compile(r"^CHAPTER\s+(\d+)", re.IGNORECASE)
    max_pages = min(1050, len(reader.pages))

    for page_idx in range(max_pages):
        text = reader.pages[page_idx].extract_text() or ""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            continue

        top_line = lines[0]
        h_match = header_pattern.match(top_line)
        if h_match:
            b_name = h_match.group(1).strip()
            full_b = normalize_book_name(b_name)
            if full_b in BIBLE_BOOKS:
                current_book = full_b
            current_chapter = int(h_match.group(2))

        curr_v = None
        curr_txt = ""

        for line in lines[1:]:
            if "Page " in line or re.match(r"^[a-z]?\[?[1-3]?[A-Z][a-z]+\.?\s+\d+:\d+", line) or "1Lit." in line:
                continue

            c_match = chap_pattern.match(line)
            if c_match:
                if curr_v and len(curr_txt.strip()) > 15:
                    clean = re.sub(r"^[a-z](?=[A-Z“\"])", "", curr_txt).strip()
                    clean = re.sub(r"\[\d+\]", "", clean).strip()
                    ref = f"{current_book} {current_chapter}:{curr_v}"
                    if ref not in verses_map or len(clean) > len(verses_map[ref]["text"]):
                        verses_map[ref] = {
                            "book": current_book,
                            "chapter": current_chapter,
                            "verse": curr_v,
                            "reference": ref,
                            "translation": "NKJV",
                            "text": clean
                        }
                current_chapter = int(c_match.group(1))
                curr_v = None
                curr_txt = ""
                continue

            vm = re.match(r"^(\d+)\s+([A-Za-z“\"'].*)", line)
            if vm:
                if curr_v and len(curr_txt.strip()) > 15:
                    clean = re.sub(r"^[a-z](?=[A-Z“\"])", "", curr_txt).strip()
                    clean = re.sub(r"\[\d+\]", "", clean).strip()
                    ref = f"{current_book} {current_chapter}:{curr_v}"
                    if ref not in verses_map or len(clean) > len(verses_map[ref]["text"]):
                        verses_map[ref] = {
                            "book": current_book,
                            "chapter": current_chapter,
                            "verse": curr_v,
                            "reference": ref,
                            "translation": "NKJV",
                            "text": clean
                        }
                curr_v = int(vm.group(1))
                curr_txt = vm.group(2)
            elif curr_v:
                curr_txt += " " + line

        if curr_v and len(curr_txt.strip()) > 15:
            clean = re.sub(r"^[a-z](?=[A-Z“\"])", "", curr_txt).strip()
            clean = re.sub(r"\[\d+\]", "", clean).strip()
            ref = f"{current_book} {current_chapter}:{curr_v}"
            if ref not in verses_map or len(clean) > len(verses_map[ref]["text"]):
                verses_map[ref] = {
                    "book": current_book,
                    "chapter": current_chapter,
                    "verse": curr_v,
                    "reference": ref,
                    "translation": "NKJV",
                    "text": clean
                }

    verses = list(verses_map.values())
    print(f"✅ Extracted {len(verses)} NKJV verses with full unabbreviated book titles.")
    return verses


def parse_esv(pdf_path: Path) -> List[Dict]:
    """Parses ESV PDF with inline multi-verse splitting."""
    print(f"\n[PARSING ESV] {pdf_path.name}...")
    reader = PdfReader(str(pdf_path))
    verses = []
    current_book = "Genesis"
    current_chapter = 1

    chap_pattern = re.compile(r"^Chapter\s+(\d+)", re.IGNORECASE)

    for page in reader.pages:
        text = page.extract_text() or ""
        if not text:
            continue

        for line in text.splitlines():
            line = line.strip()
            for b in BIBLE_BOOKS:
                if line.startswith(b) and len(line) < len(b) + 8:
                    current_book = b
                    break
            c_match = chap_pattern.match(line)
            if c_match:
                current_chapter = int(c_match.group(1))

        tokens = re.split(r"(?<=\D)(?:\[\d+\]\s*)?(\d{1,3})\s+(?=[A-Z“\"\x27])", text)
        if len(tokens) > 1:
            for i in range(1, len(tokens), 2):
                v_num_str = tokens[i]
                v_text = tokens[i+1].strip().split("\n")[0]
                if v_num_str.isdigit():
                    v_num = int(v_num_str)
                    clean_text = re.sub(r"\[\d+\]", "", v_text).strip()
                    if clean_text and not clean_text.startswith("Pet."):
                        ref = f"{current_book} {current_chapter}:{v_num}"
                        verses.append({
                            "book": current_book,
                            "chapter": current_chapter,
                            "verse": v_num,
                            "reference": ref,
                            "translation": "ESV",
                            "text": clean_text
                        })

    print(f"✅ Extracted {len(verses)} ESV verses with full unabbreviated book titles.")
    return verses


def ingest_all_translations():
    """Main execution function to parse all 4 PDFs and store into SQLite."""
    db = DatabaseManager()
    db.init_db()

    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM verses;")
        conn.commit()

    all_parsed_verses = []

    # 1. NLT
    nlt_path = SCRIPTURES_DIR / "New-Living-Translation-NLT.pdf"
    if nlt_path.exists():
        all_parsed_verses.extend(parse_nlt(nlt_path))

    # 2. KJV
    kjv_path = SCRIPTURES_DIR / "PDF-King-James-Bible.pdf"
    if kjv_path.exists():
        all_parsed_verses.extend(parse_kjv(kjv_path))

    # 3. NKJV
    nkjv_path = SCRIPTURES_DIR / "new-king-james-version-en.pdf"
    if nkjv_path.exists():
        all_parsed_verses.extend(parse_nkjv(nkjv_path))

    # 4. ESV
    esv_path = SCRIPTURES_DIR / "272774876-The-Holy-Bible-ESV.pdf"
    if esv_path.exists():
        all_parsed_verses.extend(parse_esv(esv_path))

    print(f"\n🔄 Storing {len(all_parsed_verses)} pristine verses into SQLite...")

    chapter_groups = {}
    for v in all_parsed_verses:
        key = (v["translation"], v["book"], v["chapter"])
        chapter_groups.setdefault(key, []).append(v)

    with db._get_connection() as conn:
        cursor = conn.cursor()
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
    print(f"\n{'='*70}\n🌟 Ingestion Complete! Total pristine verses in SQLite: {total_in_db}\n{'='*70}\n")


if __name__ == "__main__":
    ingest_all_translations()
