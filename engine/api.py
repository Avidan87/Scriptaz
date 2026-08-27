"""
Scriptaz FastAPI Backend Server
Exposes clean REST and SSE streaming endpoints for desktop UI, CLI, and client consumers.
Interactive Swagger API Docs available at http://127.0.0.1:8765/docs
"""

import json
import asyncio
from fastapi import FastAPI, HTTPException, Query, Path as FastPath, status
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from typing import Optional, List, Dict, Any

from core.config import config
from core.models import (
    VerseModel,
    BibleTranslation,
    ScriptureTheme,
    UserSettingsModel,
    InsightRequest,
    StructuredInsight,
    PinnedVerseModel
)
from core.db import db
from engine.bedrock_engine import bedrock_engine

app = FastAPI(
    title="Scriptaz API",
    description="Intelligent, Context-Sound Scripture Companion API powered by AWS Bedrock & SQLite",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local desktop UI / webview / frontend consumers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# 1. System & Health Endpoints
# ----------------------------------------------------------------------
@app.get("/api/health", summary="System Health Check", tags=["System"])
def health_check():
    """Checks SQLite database verse counts, AWS region, and Bedrock engine readiness."""
    verse_count = db.count_verses()
    return {
        "status": "healthy",
        "app_name": config.app_name,
        "database_verse_count": verse_count,
        "active_region": config.aws_region,
        "bedrock_model": config.bedrock_model_id,
        "embedding_model": config.bedrock_embedding_model_id,
        "bedrock_ready": bedrock_engine.client is not None
    }


@app.get("/api/themes", response_model=List[str], summary="List All 11 Scripture Themes", tags=["Metadata"])
def get_themes():
    """Returns all 11 curated biblical themes."""
    return [theme.value for theme in ScriptureTheme]


@app.get("/api/translations", response_model=List[str], summary="List Available Bible Translations", tags=["Metadata"])
def get_translations():
    """Returns available translations (KJV, NLT, NKJV, ESV)."""
    return [trans.value for trans in BibleTranslation]


# ----------------------------------------------------------------------
# 2. Scripture Retrieval & Queue Endpoints
# ----------------------------------------------------------------------
@app.get("/api/verse/next", response_model=Optional[VerseModel], summary="Get Next Queued Scripture", tags=["Verses"])
def get_next_verse():
    """Retrieves the next active workday scripture based on theme, daily limit, and sequence queue."""
    verse = db.get_next_queue_verse()
    if not verse:
        settings = db.get_settings()
        verses = db.get_verses_by_theme(settings.active_theme.value, settings.active_translation.value)
        return verses[0] if verses else None
    return verse


@app.get("/api/verse/{verse_id}", response_model=VerseModel, summary="Get Verse by ID", tags=["Verses"])
def get_verse_by_id(verse_id: int = FastPath(..., description="ID of the verse")):
    """Retrieves a specific verse by its unique integer ID."""
    verse = db.get_verse_by_id(verse_id)
    if not verse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verse with ID {verse_id} not found")
    return verse


@app.get("/api/verses/by-theme", response_model=List[VerseModel], summary="Get Verses by Theme", tags=["Verses"])
def get_verses_by_theme(
    theme: ScriptureTheme = Query(ScriptureTheme.WISDOM, description="Biblical theme to query"),
    translation: BibleTranslation = Query(BibleTranslation.KJV, description="Bible translation"),
    limit: int = Query(20, ge=1, le=100, description="Max number of verses to return")
):
    """Retrieves a list of verses matching a specific theme and translation."""
    verses = db.get_verses_by_theme(theme.value, translation.value)
    return verses[:limit]


@app.get("/api/verses/{reference}/translations", summary="Compare 4 Translations for a Reference", tags=["Verses"])
def get_verse_translations(reference: str = FastPath(..., description="Scripture reference, e.g. 'Proverbs 3:5'")):
    """Returns text across KJV, NLT, NKJV, and ESV for a given canonical scripture reference."""
    translations = db.get_all_translations_for_ref(reference)
    if not translations:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No verses found for reference: {reference}")
    return {
        "reference": reference,
        "translations": translations
    }


@app.get("/api/verses/search", response_model=List[VerseModel], summary="Semantic Vector Search", tags=["Verses"])
def search_verses(
    q: str = Query(..., description="Search query, personal struggle, or topic"),
    theme: Optional[str] = Query(None, description="Optional theme filter"),
    translation: BibleTranslation = Query(BibleTranslation.KJV, description="Bible translation"),
    limit: int = Query(5, ge=1, le=20, description="Max results")
):
    """Searches verses semantically using Bedrock Titan V2 cosine similarity matching."""
    return bedrock_engine.search_similar_verses(
        query_text=q,
        theme=theme,
        translation=translation.value,
        top_k=limit
    )


# ----------------------------------------------------------------------
# 3. Deep Insight Endpoints (Streaming SSE & Direct JSON)
# ----------------------------------------------------------------------
@app.post("/api/insight/stream", summary="Stream Deep Insight (SSE)", tags=["Deep Insights"])
async def stream_deep_insight(request: InsightRequest):
    """
    Streams DeepSeek-R1 Christ-centered illumination token-by-token over Server-Sent Events (SSE).
    Checks SQLite cache first for 0ms, $0-cost instant hits.
    """
    async def event_generator():
        async for chunk in bedrock_engine.stream_insight(request):
            yield {
                "event": "insight_chunk",
                "data": json.dumps(chunk)
            }

    return EventSourceResponse(event_generator())


@app.post("/api/insight", response_model=StructuredInsight, summary="Get Deep Insight (Direct JSON)", tags=["Deep Insights"])
async def get_direct_insight(request: InsightRequest):
    """Generates or retrieves cached Deep Insight, returning the complete structured result in a single JSON response."""
    final_insight = None
    async for chunk in bedrock_engine.stream_insight(request):
        if chunk.get("type") in ("complete", "cached", "fallback"):
            data = chunk.get("insight", {})
            final_insight = StructuredInsight(**data)
            break
    
    if not final_insight:
        final_insight = bedrock_engine._generate_local_fallback(request)
    return final_insight


# ----------------------------------------------------------------------
# 4. User Settings & Preferences Endpoints
# ----------------------------------------------------------------------
@app.get("/api/settings", response_model=UserSettingsModel, summary="Get User Settings", tags=["Settings"])
def get_user_settings():
    """Returns the user's current preferences (user name, interval, daily limit, theme, struggle context)."""
    return db.get_settings()


@app.post("/api/settings", response_model=UserSettingsModel, summary="Update User Settings", tags=["Settings"])
def update_user_settings(settings: UserSettingsModel):
    """Updates user preferences (user name, interval minutes, daily limit, active theme, personal struggle context)."""
    db.update_settings(settings)
    return db.get_settings()


# ----------------------------------------------------------------------
# 5. Pinned Verses ("My Verses") Endpoints
# ----------------------------------------------------------------------
@app.get("/api/verses/pinned", response_model=List[PinnedVerseModel], summary="List All Pinned Verses", tags=["Pinned Verses"])
def list_pinned_verses():
    """Returns the user's saved 'My Verses' archive."""
    return db.get_pinned_verses()


@app.post("/api/verses/{verse_id}/pin", summary="Pin a Verse into Rotation", tags=["Pinned Verses"])
def pin_verse(
    verse_id: int = FastPath(..., description="Verse ID to pin"),
    notes: Optional[str] = Query(None, description="Optional personal reflection note")
):
    """Pins a verse into active workday rotation and saves it in the archive."""
    success = db.pin_verse(verse_id, notes)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verse not found")
    return {"status": "success", "message": f"Verse {verse_id} pinned successfully", "verse_id": verse_id}


@app.delete("/api/verses/{verse_id}/pin", summary="Unpin a Verse", tags=["Pinned Verses"])
def unpin_verse(verse_id: int = FastPath(..., description="Verse ID to unpin")):
    """Removes a verse from pinned rotation."""
    success = db.unpin_verse(verse_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verse was not pinned")
    return {"status": "success", "message": f"Verse {verse_id} unpinned successfully", "verse_id": verse_id}


def run_server():
    """Runs the FastAPI server via uvicorn."""
    import uvicorn
    uvicorn.run(app, host=config.api_host, port=config.api_port)


if __name__ == "__main__":
    run_server()
