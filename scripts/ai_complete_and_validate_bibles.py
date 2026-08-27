"""
Scriptaz AI-Powered Bible Auto-Healer & Canonical Completer
Scans SQLite for all 66 books and 4 translations (KJV, NLT, NKJV, ESV).
Uses Strict Smart-Skip ($0 cost for healthy verses) and batches defective/missing
verses to AWS Bedrock DeepSeek-R1 with 4096-token headroom and fault-tolerant parsing.
"""

import sys
import json
import re
import time
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config
from core.db import db
from engine.bedrock_engine import bedrock_engine


def is_text_healthy(text: Optional[str]) -> bool:
    """Returns True if the verse text is healthy, complete, and free of footnote artifacts."""
    if not text or len(text.strip()) < 25:
        return False
    t = text.strip()
    # Check for footnote artifacts
    if re.match(r"^[a-z]?\[?[1-3]?[A-Z][a-z]+\.?\s+\d+:\d+", t) or "1Lit." in t or t.startswith("Page "):
        return False
    if t.startswith("a[") or t.startswith("b[") or t.startswith("c[") or t.startswith("Greek in the"):
        return False
    return True


def extract_verses_from_ai_response(output_text: str) -> Dict[Tuple[str, str], str]:
    """Robustly extracts (reference, translation) -> text, handling unescaped quotes."""
    result = {}

    # 1. Try standard JSON parse
    json_match = re.search(r"\{[\s\S]*\}", output_text)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            for k, text_val in data.items():
                m = re.match(r"^(.*?)\s*\((KJV|NLT|NKJV|ESV)\)$", k.strip(), re.IGNORECASE)
                if m and isinstance(text_val, str):
                    ref = m.group(1).strip()
                    trans = m.group(2).strip().upper()
                    result[(ref, trans)] = text_val.strip()
            if result:
                return result
        except Exception:
            pass

    # 2. Fault-Tolerant Line-by-Line Regex Parser (handles internal unescaped quotes)
    pattern = re.compile(r'"([^"]+?\s*\((?:KJV|NLT|NKJV|ESV)\))"\s*:\s*"([\s\S]*?)(?="\s*,\s*"|"\s*\}|\n\s*\}|\n\s*"|$)', re.MULTILINE)
    matches = pattern.findall(output_text)
    for k, v in matches:
        m = re.match(r"^(.*?)\s*\((KJV|NLT|NKJV|ESV)\)$", k.strip(), re.IGNORECASE)
        if m:
            ref = m.group(1).strip()
            trans = m.group(2).strip().upper()
            clean_val = v.replace('\\"', '"').replace('\\n', ' ').strip()
            if len(clean_val) >= 10:
                result[(ref, trans)] = clean_val

    return result


def heal_batch(client, batch_items: List[Tuple[str, str, str, int, int]]) -> Dict[Tuple[str, str], str]:
    """
    Sends a batch of (reference, translation, book, chapter, verse) to DeepSeek-R1
    and returns a mapping of (reference, translation) -> pristine canonical text.
    """
    if not batch_items or not client:
        return {}

    ref_list_str = "\n".join(f"- {ref} ({trans})" for ref, trans, _, _, _ in batch_items)
    prompt = f"""You are a precise, word-for-word canonical Bible archivist.
Provide the exact, complete, unabbreviated canonical text for each requested Scripture reference and translation.
Do NOT include commentary, introductions, markdown headers, or explanations.

Requested Verses:
{ref_list_str}

Output strictly valid JSON mapping "[Reference] ([Translation])" to its exact verse text:
{{
  "Philippians 4:6 (NKJV)": "Be anxious for nothing, but in everything by prayer and supplication, with thanksgiving, let your requests be made known to God;",
  ...
}}"""

    try:
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        response = client.converse(
            modelId=config.bedrock_model_id,
            messages=messages,
            inferenceConfig={"temperature": 0.0, "maxTokens": 4096}
        )

        content = response["output"]["message"]["content"]
        output_text = ""
        for c in content:
            if "text" in c:
                output_text += c["text"]

        return extract_verses_from_ai_response(output_text)
    except Exception as e:
        print(f"\n⚠️ Batch AI healing warning: {e}")
    return {}


def run_ai_auto_healing(limit_repairs: Optional[int] = None, batch_size: int = 25, concurrency: int = 8):
    print(f"\n{'='*70}\n[SCRIPTAZ AI-POWERED BIBLE AUTO-HEALER & COMPLETION ENGINE]\n{'='*70}")
    
    client = bedrock_engine.client
    if not client:
        print("❌ Error: AWS Bedrock client not initialized. Check your .env credentials.")
        return

    # 1. Scan SQLite for all distinct references and audit translation health
    print("🔍 Performing Zero-Cost Local SQLite Health Scan across all 4 translations...")
    
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT reference, book, chapter, verse FROM verses ORDER BY id ASC")
        all_canonical_refs = cursor.fetchall()
        
        cursor.execute("SELECT reference, translation, text FROM verses")
        existing_rows = cursor.fetchall()

    ref_trans_map = {}
    for r in existing_rows:
        ref_trans_map[(r["reference"], r["translation"])] = r["text"]

    translations = ["KJV", "NLT", "NKJV", "ESV"]
    defective_items = []
    healthy_count = 0

    for r in all_canonical_refs:
        ref = r["reference"]
        book = r["book"]
        chap = r["chapter"]
        v_num = r["verse"]

        for trans in translations:
            text = ref_trans_map.get((ref, trans))
            if is_text_healthy(text):
                healthy_count += 1
            else:
                defective_items.append((ref, trans, book, chap, v_num))

    print(f"✅ Healthy, Complete Verses Found: {healthy_count} (Skipped for $0.00 Cost)")
    print(f"🔄 Incomplete / Missing Verses Queued for AI Healing: {len(defective_items)}")

    if not defective_items:
        print("\n🎉 The database is already 100% complete and pristine! Zero AI calls needed.")
        return

    if limit_repairs:
        defective_items = defective_items[:limit_repairs]
        print(f"⚙️ Running with repair limit: {limit_repairs} items")

    # 2. Batch Defective Items into groups of 25
    batches = [defective_items[i:i + batch_size] for i in range(0, len(defective_items), batch_size)]
    print(f"📦 Grouped {len(defective_items)} items into {len(batches)} efficient AI batches (Batch size: {batch_size})")
    print(f"🚀 Starting parallel AI auto-healing with {concurrency} workers (4096 token headroom)...\n")

    repaired_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(heal_batch, client, b): b for b in batches}

        for idx, f in enumerate(as_completed(futures)):
            orig_batch = futures[f]
            batch_result = f.result()

            if batch_result:
                with db._get_connection() as conn:
                    cursor = conn.cursor()
                    for (ref, trans, book, chap, v_num) in orig_batch:
                        healed_text = batch_result.get((ref, trans))
                        if healed_text and len(healed_text) >= 15:
                            cursor.execute("""
                                INSERT INTO verses (
                                    book, chapter, verse, reference, translation, text, theme,
                                    surrounding_context, tags
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(reference, translation) DO UPDATE SET
                                    text = excluded.text
                            """, (
                                book,
                                chap,
                                v_num,
                                ref,
                                trans,
                                healed_text,
                                "Sin & Grace",
                                f"{book} Chapter {chap}",
                                json.dumps([book, f"Chapter {chap}"])
                            ))
                            repaired_count += 1
                    conn.commit()

            elapsed = time.time() - start_time
            rate = (idx + 1) / max(1, elapsed)
            percent = ((idx + 1) / len(batches)) * 100
            sys.stdout.write(f"\r⚡ AI Healing: Batch {idx+1}/{len(batches)} ({percent:.1f}%) | Repaired: {repaired_count} verses | Speed: {rate:.1f} batches/sec")
            sys.stdout.flush()

    total_in_db = db.count_verses()
    print(f"\n\n{'='*70}\n🌟 AI AUTO-HEALING COMPLETE!\n{'='*70}")
    print(f"🎉 Successfully repaired & stored {repaired_count} canonical verses into SQLite.")
    print(f"📊 Total pristine verses in database: {total_in_db}")
    print(f"⏱️ Time elapsed: {time.time() - start_time:.2f} seconds.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scriptaz AI Database Auto-Healer")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of verses to repair")
    parser.add_argument("--batch-size", type=int, default=25, help="Number of verses per AI request")
    parser.add_argument("--concurrency", type=int, default=8, help="Number of concurrent AI workers")
    args = parser.parse_args()

    run_ai_auto_healing(limit_repairs=args.limit, batch_size=args.batch_size, concurrency=args.concurrency)
