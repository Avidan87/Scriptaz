"""
Scriptaz Batch Vector Embedding Generator
Embeds Bible verses from SQLite using Amazon Bedrock Titan Text Embeddings V2
and saves the dense 512-dimension binary vectors directly into SQLite (verses.embedding_blob).
Supports progress tracking, batch commits, rate-limit safety, and auto-resume.
"""

import sys
import time
import json
import argparse
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config
from core.db import db
from engine.bedrock_engine import bedrock_engine


def embed_single_verse(verse_id: int, text_payload: str) -> Tuple[int, Optional[np.ndarray]]:
    """Calls Bedrock Titan V2 for a single verse payload."""
    vec = bedrock_engine.generate_embedding(text_payload)
    return verse_id, vec


def run_embedding_pipeline(
    limit: Optional[int] = None,
    theme_filter: Optional[str] = None,
    translations: Optional[List[str]] = None,
    concurrency: int = 12
):
    print(f"\n{'='*75}\n[SCRIPTAZ VECTOR EMBEDDING PIPELINE (Bedrock Titan V2)]\n{'='*75}")
    
    if not bedrock_engine.client:
        print("❌ Error: AWS Bedrock client not initialized. Please verify AWS credentials in .env")
        return

    with db._get_connection() as conn:
        cursor = conn.cursor()
        
        # Build query for target verses without embeddings
        query = "SELECT id, reference, translation, text, surrounding_context, theme FROM verses WHERE embedding_blob IS NULL"
        params = []
        
        if translations:
            placeholders = ",".join("?" for _ in translations)
            query += f" AND translation IN ({placeholders})"
            params.extend(translations)
            
        if theme_filter:
            query += " AND theme = ?"
            params.append(theme_filter)
            
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query, params)
        rows = cursor.fetchall()

    total_to_embed = len(rows)
    target_trans_str = ", ".join(translations) if translations else "All"
    if total_to_embed == 0:
        print(f"✅ All matching verses ({target_trans_str}) in SQLite are already embedded! No work needed.")
        return

    print(f"🎯 Target Translations: {target_trans_str}")
    print(f"🔄 Queued for Embedding: {total_to_embed:,} verses")
    print(f"⚙️ Model: {config.bedrock_embedding_model_id} | Dimensions: 512 | Concurrency: {concurrency} workers\n")

    batch_size = 50
    completed = 0
    start_time = time.time()
    pending_updates = []

    # Process in worker pool
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {}
        for r in rows:
            v_id = r["id"]
            payload = f"[{r['reference']} - {r['translation']}] Theme: {r['theme']}. Verse: {r['text']}. Narrative Context: {r['surrounding_context'] or r['text']}"
            f = executor.submit(embed_single_verse, v_id, payload)
            futures[f] = v_id

        for f in as_completed(futures):
            v_id, vec = f.result()
            if vec is not None:
                pending_updates.append((vec.tobytes(), v_id))
            completed += 1

            # Batch write to SQLite
            if len(pending_updates) >= batch_size or completed == total_to_embed:
                with db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.executemany(
                        "UPDATE verses SET embedding_blob = ? WHERE id = ?",
                        pending_updates
                    )
                    conn.commit()
                pending_updates = []

            # Progress output
            elapsed = time.time() - start_time
            rate = completed / max(1, elapsed)
            percent = (completed / total_to_embed) * 100
            sys.stdout.write(f"\r🚀 Progress: {completed:,}/{total_to_embed:,} ({percent:.1f}%) | Speed: {rate:.1f} verses/sec")
            sys.stdout.flush()

    total_time = time.time() - start_time
    print(f"\n\n🎉 Successfully generated and saved {completed:,} embeddings to SQLite!")
    print(f"⏱️ Total time elapsed: {total_time:.2f} seconds ({completed/max(1, total_time):.1f} verses/sec).\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Bedrock Titan V2 embeddings for Bible verses")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of verses to embed")
    parser.add_argument("--theme", type=str, default=None, help="Filter by specific theme (e.g. 'Wisdom')")
    parser.add_argument("--translations", type=str, default="NKJV,NLT", help="Comma-separated translations (e.g. 'NKJV,NLT')")
    parser.add_argument("--concurrency", type=int, default=12, help="Concurrent AWS Bedrock worker threads")
    args = parser.parse_args()

    trans_list = [t.strip().upper() for t in args.translations.split(",") if t.strip()] if args.translations else None
    run_embedding_pipeline(limit=args.limit, theme_filter=args.theme, translations=trans_list, concurrency=args.concurrency)
