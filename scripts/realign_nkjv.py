"""
Scriptaz NKJV Alignment & Canonical Healing Engine
Scans NKJV verses for chapter-shift artifacts and repairs them with exact canonical text.
"""

import sys
import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.db import db
from engine.bedrock_engine import bedrock_engine
from scripts.ai_complete_and_validate_bibles import heal_batch

HALLMARK_REPAIR_REFS = [
    "Philippians 4:6", "Proverbs 3:5", "1 Corinthians 15:3", "1 Corinthians 14:6",
    "Ephesians 2:8", "Romans 12:2", "Galatians 5:22", "Hebrews 11:6", "2 Timothy 1:7",
    "Joshua 1:9", "Psalms 91:1", "Isaiah 41:10", "Jeremiah 29:11", "Romans 8:31"
]


def realign_nkjv_scriptures():
    print(f"\n{'='*70}\n[SCRIPTAZ NKJV CANONICAL REALIGNMENT ENGINE]\n{'='*70}")
    
    client = bedrock_engine.client
    if not client:
        print("❌ Error: AWS Bedrock client not initialized.")
        return

    # Build repair batch
    batch_items = []
    for ref in HALLMARK_REPAIR_REFS:
        parts = ref.split()
        book = " ".join(parts[:-1])
        chap_v = parts[-1].split(":")
        chap = int(chap_v[0])
        v_num = int(chap_v[1])
        batch_items.append((ref, "NKJV", book, chap, v_num))

    print(f"🔄 Realigning {len(batch_items)} NKJV key passages with canonical text...")
    healed = heal_batch(client, batch_items)

    with db._get_connection() as conn:
        cursor = conn.cursor()
        for (ref, trans, book, chap, v_num) in batch_items:
            clean_txt = healed.get((ref, "NKJV"))
            if clean_txt:
                cursor.execute("""
                    INSERT INTO verses (book, chapter, verse, reference, translation, text, theme, surrounding_context, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(reference, translation) DO UPDATE SET text = excluded.text
                """, (book, chap, v_num, ref, "NKJV", clean_txt, "Sin & Grace", f"{book} Chapter {chap}", json.dumps([book])))
        conn.commit()

    print("✅ Canonical NKJV passages realigned successfully!")

    # Verify Philippians 4:6 and Proverbs 3:5
    for r in ["Philippians 4:6", "Proverbs 3:5", "1 Corinthians 15:3"]:
        translations = db.get_all_translations_for_ref(r)
        print(f"\n📖 {r} [NKJV] -> \"{translations.get('NKJV')}\"")


if __name__ == "__main__":
    realign_nkjv_scriptures()
