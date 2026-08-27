"""
Scriptaz AWS Bedrock Engine
Integrates Amazon Bedrock Titan Text Embeddings V2 and DeepSeek-R1
for vector similarity matching, dynamic prompt synthesis, and live token-streamed expositions.
Enforces short, airy 2-sentence micro-paragraphs with clean spacing, personal user name, and zero walls of text.
"""

import json
import re
import sys
import numpy as np
from typing import AsyncGenerator, Generator, Optional, List, Dict, Any, Tuple
from datetime import datetime

from core.config import config
from core.models import (
    VerseModel,
    BibleTranslation,
    ScriptureTheme,
    InsightRequest,
    StructuredInsight
)
from core.db import db, DatabaseManager


SYSTEM_PROMPT = """You are a warm, wise, and deeply empathetic brother in Christ.

YOUR HEART & MISSION:
Speak directly, warmly, and personally to your brother or sister in Christ about this Scripture passage. Speak with genuine care, wisdom, and empathy, anchoring your thoughts on the selected theme and their real-time workday situation.

STRICT FORMATTING & BREVITY RULES:

1. PERSONAL & DYNAMIC INSPIRATION (ZERO BOILERPLATE):
   - Greet the user by their first name naturally at the start.
   - Any theme guidelines are purely conceptual sources of inspiration for your heart—NEVER copy canned phrases, boilerplate formulas, or repetitive cliches.
   - Intelligently and organically connect the theme and passage to Jesus Christ without being forced, preachy, or repetitive.

2. SHORT, AIRY MICRO-PARAGRAPHS (STRICTLY NO WALLS OF TEXT):
   - Every paragraph MUST be short (maximum 1 to 2 sentences).
   - Insert a double line break between distinct thoughts so the text has plenty of breathing room.
   - Keep the entire reflection ultra-crisp and concise (around 90 to 110 words total, readable in under 20 seconds).

3. NO EMOJIS & NO ARTIFICIAL SECTION HEADINGS:
   - Do NOT use emojis anywhere in your response.
   - Do NOT use artificial section titles or headers (do NOT write "### Context", "Section 1", or "### Application").

4. CONVERSATIONAL FLOW:
   - Paragraph 1 (1-2 sentences): Personal greeting addressing them by name, warmly acknowledging their real situation and passage setting.
   - Paragraph 2 (1-2 sentences): Simple, reassuring truth of God's Word and how Jesus meets them right here today.
   - Paragraph 3 (1-2 sentences): Practical encouragement and comfort for their workday.
   - Companion Scriptures: Introduce cleanly with "Scriptures that flow with this truth:" followed by clean bullet points with brief 1-line takeaways.
   - Closing Blessing (1 short line): A brief, uplifting brotherly encouragement.
"""


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

    # ----------------------------------------------------------------------
    # 2. Deep Insights (DeepSeek-R1 Token Streaming)
    # ----------------------------------------------------------------------
    def build_user_prompt(self, request: InsightRequest) -> str:
        """Constructs the dynamic user prompt payload."""
        user_name = request.user_name or self.db.get_settings().user_name or "Friend"
        context_str = request.personal_context.strip() if request.personal_context else "General workday reflection"

        return f"""Please share an encouraging, relatable reflection for this scripture:

User's Name: {user_name}
Scripture Reference: {request.reference}
Translation: {request.translation.value if hasattr(request.translation, 'value') else request.translation}
Verse Text: "{request.verse_text}"

Surrounding Chapter Context:
{request.surrounding_context or "Immediate chapter setting of " + request.reference}

Active Focus Theme: {request.active_theme}
User's Real-Time Situation: {context_str}

Remember:
- Address {user_name} warmly by first name.
- Keep paragraphs short (1 to 2 sentences max) with double line breaks between thoughts.
- Total length: ~90 to 110 words total.
- Do not use emojis.
- Do not use artificial section titles or headers."""

    async def stream_insight(
        self,
        request: InsightRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams DeepSeek-R1 exposition live.
        Checks SQLite cache first (0ms hit, $0 cost).
        Yields chunk dictionaries: {"type": "token", "content": "..."} or {"type": "complete", "insight": {...}}
        """
        cache_key = self.db.generate_cache_key(
            reference=request.reference,
            translation=request.translation.value if hasattr(request.translation, 'value') else str(request.translation),
            theme=request.active_theme,
            personal_context=request.personal_context
        )

        # 1. Check SQLite Cache
        cached_insight = self.db.get_cached_insight(cache_key)
        if cached_insight:
            yield {
                "type": "cached",
                "insight": cached_insight.model_dump(),
                "cache_key": cache_key
            }
            return

        # 2. If Miss & No AWS Client, Fallback Gracefully
        if not self.client:
            fallback_insight = self._generate_local_fallback(request)
            yield {
                "type": "fallback",
                "insight": fallback_insight.model_dump(),
                "message": "Offline Mode — Local reflection generated."
            }
            return

        # 3. Call Amazon Bedrock DeepSeek-R1 Streaming
        user_prompt = self.build_user_prompt(request)
        full_text = ""

        try:
            messages = [
                {"role": "user", "content": [{"text": user_prompt}]}
            ]
            
            response = self.client.converse_stream(
                modelId=config.bedrock_model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=messages,
                inferenceConfig={"temperature": 0.4, "maxTokens": 2048}
            )

            stream = response.get("stream")
            if stream:
                for event in stream:
                    if "contentBlockDelta" in event:
                        delta_dict = event["contentBlockDelta"].get("delta", {})
                        
                        # Handle reasoning content vs final text delta
                        if "text" in delta_dict:
                            delta_text = delta_dict["text"]
                            full_text += delta_text
                            yield {
                                "type": "token",
                                "delta": delta_text,
                                "full_text": full_text
                            }
                        elif "reasoningContent" in delta_dict:
                            continue

            # 4. Clean formatting
            clean_output = full_text.strip()

            # Extract cross references if present
            ref_matches = re.findall(r"([1-3]?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+\d+:\d+(?:-\d+)?)", clean_output)
            connected_scriptures = list(dict.fromkeys(ref_matches))[:3]

            structured = StructuredInsight(
                context_and_setting="",
                original_word_illumination="",
                christ_centered_revelation=clean_output,
                connected_scriptures=connected_scriptures,
                is_cached=False,
                model_used=config.bedrock_model_id,
                cached_at=datetime.now()
            )

            # 5. Save into SQLite Cache (0ms on next lookup)
            self.db.save_cached_insight(
                cache_key=cache_key,
                verse_ref=request.reference,
                translation=request.translation.value if hasattr(request.translation, 'value') else str(request.translation),
                theme=request.active_theme,
                personal_context=request.personal_context,
                raw_output=clean_output,
                insight=structured,
                model_used=config.bedrock_model_id
            )

            yield {
                "type": "complete",
                "insight": structured.model_dump(),
                "cache_key": cache_key
            }

        except Exception as e:
            print(f"Bedrock streaming exception: {e}")
            fallback_insight = self._generate_local_fallback(request)
            yield {
                "type": "fallback",
                "insight": fallback_insight.model_dump(),
                "error": str(e)
            }

    def _generate_local_fallback(self, request: InsightRequest) -> StructuredInsight:
        """Offline fallback reflection when internet/AWS is unreachable."""
        user_name = request.user_name or self.db.get_settings().user_name or "Friend"
        text = (
            f"Hey {user_name}, when you are carrying {request.personal_context or 'a lot on your mind'}, "
            f"it is easy to feel the weight of every task.\n\n"
            f"In {request.reference}, God reminds us that we don't have to figure out everything in our own strength today. "
            f"His grace meets you right in the middle of your work.\n\n"
            f"Scriptures that flow with this truth:\n\n"
            f"• Philippians 4:6-7 — Bring every request to God and let His peace guard your heart.\n"
            f"• Proverbs 3:5-6 — Trusting in the Lord with all your heart as He directs your steps.\n\n"
            f"Take a deep breath, {user_name}. Walk in confidence knowing He is with you."
        )
        return StructuredInsight(
            context_and_setting="",
            original_word_illumination="",
            christ_centered_revelation=text,
            connected_scriptures=["Philippians 4:6-7", "Proverbs 3:5-6"],
            is_cached=False,
            model_used="Local-Fallback",
            cached_at=datetime.now()
        )


# Global Bedrock Engine Instance
bedrock_engine = BedrockEngine()
