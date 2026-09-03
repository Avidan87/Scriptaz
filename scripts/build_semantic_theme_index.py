"""
Scriptaz Semantic Theme Index Builder
Computes dense cosine similarity across all 124,352 Bible verses (KJV, NKJV, ESV, NLT)
against rich theological profiles for the 5 flagship preset themes:
Peace, Wisdom, Faith, Grace, Provision.
Populates the theme_semantic_index table for instant, zero-latency local queries.
"""

import sys
import time
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.db import db
from engine.bedrock_engine import bedrock_engine

THEME_DEFINITIONS = {
    "Peace": (
        "peace of God guarding hearts, peace I leave with you, perfect peace whose mind is stayed on You, "
        "freedom from anxiety and fear, quiet stillness and rest in Christ, the God of peace, reconciled through Christ"
    ),
    "Wisdom": (
        "the fear of the Lord is the beginning of wisdom, godly discernment and understanding, wisdom from above "
        "is pure peaceable and gentle, walking in prudence and knowledge, righteous counsel, trusting in the Lord with all your heart"
    ),
    "Faith": (
        "faith is the substance of things hoped for the evidence of things not seen, trusting God's promises, "
        "walking by faith and not by sight, steadfast belief without doubting, faith pleasing to God, standing firm in Christ"
    ),
    "Grace": (
        "by grace you have been saved through faith, unmerited favor and mercy of God, grace that is sufficient in weakness, "
        "redemption through the blood of Christ Jesus, forgiveness of sins, justified freely by His grace"
    ),
    "Provision": (
        "my God shall supply all your need according to His riches in glory, the Lord is my shepherd I shall not want, "
        "daily bread, seeking first the kingdom of God, trusting God as provider Jehovah Jireh, blessing on the work of hands, contentment"
    )
}

def build_index():
    print("=" * 70)
    print("Building Semantic Theme Index across 124,352 verses...")
    print("=" * 70)

    # 1. Create table and index
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS theme_semantic_index (
                theme TEXT NOT NULL,
                verse_id INTEGER NOT NULL,
                score REAL NOT NULL,
                PRIMARY KEY(theme, verse_id)
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_theme_semantic_lookup ON theme_semantic_index(theme, score DESC);")
        cursor.execute("DELETE FROM theme_semantic_index;")
        conn.commit()

    # 2. Generate theme embeddings
    print("Generating dense embeddings for the 5 flagship themes...")
    theme_vectors = {}
    for theme_name, description in THEME_DEFINITIONS.items():
        vec = bedrock_engine.generate_embedding(description)
        if vec is not None:
            theme_vectors[theme_name] = vec
            print(f"  ✓ {theme_name}: generated 512-dim vector")
        else:
            print(f"  ❌ Failed to generate vector for {theme_name}")

    if not theme_vectors:
        print("❌ Error: Could not generate theme vectors. Check AWS credentials.")
        return

    # 3. Load all verse embeddings
    print("\nLoading verse embedding vectors from SQLite...")
    t0 = time.time()
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, translation, embedding_blob FROM verses WHERE embedding_blob IS NOT NULL")
        rows = cursor.fetchall()
    
    verse_ids = [r["id"] for r in rows]
    total_verses = len(verse_ids)
    print(f"Loaded {total_verses:,} verses in {time.time() - t0:.2f}s")

    matrix = np.vstack([np.frombuffer(r["embedding_blob"], dtype=np.float32) for r in rows])
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1e-10
    matrix_norm = matrix / norms[:, None]

    # 4. Compute similarities and batch insert
    print("\nComputing cosine similarities and indexing qualified scriptures...")
    min_threshold = 0.35
    total_indexed = 0

    for theme_name, t_vec in theme_vectors.items():
        t_norm = t_vec / np.linalg.norm(t_vec)
        scores = np.dot(matrix_norm, t_norm)
        
        qualifying = np.where(scores >= min_threshold)[0]
        records = [(theme_name, verse_ids[i], float(scores[i])) for i in qualifying]
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO theme_semantic_index (theme, verse_id, score) VALUES (?, ?, ?)",
                records
            )
            conn.commit()
            
        total_indexed += len(records)
        print(f"  ✓ {theme_name:<12}: indexed {len(records):,} scriptures (highest score: {float(np.max(scores)):.3f})")

    print("\n" + "=" * 70)
    print(f"🎉 Done! Successfully indexed {total_indexed:,} authentic scripture matches across 5 themes.")
    print("=" * 70)

if __name__ == "__main__":
    build_index()
