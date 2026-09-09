"""
Scriptaz AWS Bedrock Engine
Integrates Amazon Bedrock Titan Text Embeddings V2 for vector similarity
matching and provides text generation used by the custom-theme architect.
"""

import json
import numpy as np
from typing import Optional, List

from core.config import config
from core.models import (
    VerseModel,
    BibleTranslation,
    ScriptureTheme
)
from core.db import db, DatabaseManager


class BedrockEngine:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or db
        self.session = config.get_boto3_session()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = self.session.client("bedrock-runtime", region_name=config.aws_region)
            except Exception as e:
                print(f"⚠️ Warning: Could not initialize Bedrock client: {e}")
                self._client = None
        return self._client

    # ----------------------------------------------------------------------
    # 1. Vector Embeddings (Titan V2)
    # ----------------------------------------------------------------------
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024) -> str:
        """Calls Amazon Bedrock model (DeepSeek-R1 / Nova-Lite) for non-streaming structured text generation."""
        if not self.client:
            raise RuntimeError("AWS Bedrock client not initialized.")

        messages = [{"role": "user", "content": [{"text": prompt}]}]
        sys_block = [{"text": system_prompt}] if system_prompt else []
        
        response = self.client.converse(
            modelId=config.bedrock_model_id,
            system=sys_block,
            messages=messages,
            inferenceConfig={"temperature": 0.3, "maxTokens": max_tokens}
        )
        
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        text_parts = [b.get("text", "") for b in content_blocks if "text" in b]
        return "".join(text_parts).strip()

    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Calls Bedrock Titan Text Embeddings V2 to generate a 512-dim vector."""
        if not self.client:
            return None

        try:
            body = json.dumps({
                "inputText": text[:4000],
                "dimensions": 512,
                "normalize": True
            })
            response = self.client.invoke_model(
                modelId=config.bedrock_embedding_model_id,
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response["body"].read())
            vector = np.array(response_body["embedding"], dtype=np.float32)
            return vector
        except Exception as e:
            print(f"Embedding error: {e}")
            return None

    def search_similar_verses(
        self,
        query_text: str,
        theme: Optional[str] = None,
        translation: str = "KJV",
        top_k: int = 5
    ) -> List[VerseModel]:
        """Performs local cosine similarity matching across stored SQLite verses."""
        query_vector = self.generate_embedding(query_text)
        if query_vector is None:
            theme_name = theme or "Sin & Grace"
            return self.db.get_verses_by_theme(theme_name, translation)[:top_k]

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            if theme:
                cursor.execute(
                    "SELECT id, embedding_blob FROM verses WHERE theme = ? AND translation = ? AND embedding_blob IS NOT NULL",
                    (theme, translation)
                )
            else:
                cursor.execute(
                    "SELECT id, embedding_blob FROM verses WHERE translation = ? AND embedding_blob IS NOT NULL",
                    (translation,)
                )
            rows = cursor.fetchall()

            if not rows:
                theme_name = theme or "Sin & Grace"
                return self.db.get_verses_by_theme(theme_name, translation)[:top_k]

            ids = []
            vectors = []
            for r in rows:
                ids.append(r["id"])
                vec = np.frombuffer(r["embedding_blob"], dtype=np.float32)
                vectors.append(vec)

            matrix = np.array(vectors)
            scores = np.dot(matrix, query_vector)
            top_indices = np.argsort(scores)[::-1][:top_k]

            matched_verses = []
            for idx in top_indices:
                v = self.db.get_verse_by_id(ids[idx])
                if v:
                    matched_verses.append(v)
            return matched_verses


# Global Bedrock Engine Instance
bedrock_engine = BedrockEngine()
