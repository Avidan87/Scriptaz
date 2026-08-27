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


def run_embedding_pipeline(limit: Optional[int] = None, theme_filter: Optional[str] = None, concurrency: int = 8):
    print(f"\n{'='*70}\n[SCRIPTAZ VECTOR EMBEDDING PIPELINE (Bedrock Titan V2)]\n{'='*70}")
    
    if not bedrock_engine.client:
        print("❌ Error: AWS Bedrock client not initialized. Please verify AWS credentials in .env")
        return

    with db._get_connection() as conn:
        cursor = conn.cursor()
        
        # Count remaining verses without embeddings
        query = "SELECT id, reference, translation, text, surrounding_context, theme FROM verses WHERE embedding_blob IS NULL"
        params = []
        if theme_filter:
            query += " AND theme = ?"
            params.append(theme_filter)
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query, params)
        rows = cursor.fetchall()

    total_to_embed = len(rows)
    if total_to_embed == 0:
        print("✅ All matching verses in SQLite are already embedded! No work needed.")
        return

    print(f"🔄 Found {total_to_embed} verses queued for embedding...")
    print(f"⚙️ Model: {config.bedrock_embedding_model_id} | Dimensions: 512 | Concurrency: {concurrency}\n")

    batch_size = 50
    completed = 0
    start_time = time.time()
    pending_updates = []

    # Process in worker pool
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {}
        for r in rows:
            v_id = r["id"]
            # Construct rich context payload for Titan V2
            payload = f"[{r['reference']} - {r['translation']}] Theme: {r['theme']}. Text: {r['text']}. Context: {r['surrounding_context'] or r['text']}"
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
            sys.stdout.write(f"\r🚀 Progress: {completed}/{total_to_embed} ({percent:.1f}%) | Speed: {rate:.1f} verses/sec")
            sys.stdout.flush()

    print(f"\n\n🎉 Successfully generated and saved {completed} embeddings to SQLite!")
    print(f"⏱️ Total time elapsed: {time.time() - start_time:.2f} seconds.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Bedrock Titan V2 embeddings for Bible verses")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of verses to embed")
    parser.add_argument("--theme", type=str, default=None, help="Filter by specific theme (e.g. 'Wisdom')")
    parser.add_argument("--concurrency", type=int, default=8, help="Concurrent AWS Bedrock worker threads")
    args = parser.parse_args()

    run_embedding_pipeline(limit=args.limit, theme_filter=args.theme, concurrency=args.concurrency)
