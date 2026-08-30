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

from pydantic import BaseModel, Field
from core.config import config
from core.models import (
    VerseModel,
    BibleTranslation,
    ScriptureTheme,
    UserSettingsModel,
    CustomThemeModel,
    InsightRequest,
    StructuredInsight,
    PinnedVerseModel
)
from core.db import db
from engine.bedrock_engine import bedrock_engine
from engine.theme_architect import theme_architect

app = FastAPI(
    title="Scriptaz API",
    description="Intelligent Scripture Companion API with 5 Flagship Themes, AI Custom Themes, and 7-Day Pinned Verses Lifecycle",
    version="2.0.0",
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


class CustomThemeCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=1000, description="User's situation, struggle, or focus in plain text")
    preferred_translation: BibleTranslation = Field(default=BibleTranslation.NKJV, description="Target translation for vector search")


class ExtendedVerseResponse(BaseModel):
    id: Optional[int] = None
    book: str
    chapter: int
    verse: int
    reference: str
    translation: BibleTranslation
    text: str
    theme: str
    is_pinned: bool = False
    active_theme_display: Optional[str] = None


# ----------------------------------------------------------------------
# 1. System & Metadata Endpoints
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


@app.get("/api/themes", response_model=List[str], summary="List 5 Flagship Scripture Themes", tags=["Metadata"])
def get_themes():
    """Returns the 5 single-word flagship themes (Peace, Wisdom, Faith, Grace, Provision)."""
    return [t.value for t in ScriptureTheme if t != ScriptureTheme.CUSTOM]


@app.get("/api/translations", response_model=List[str], summary="List Available Bible Translations", tags=["Metadata"])
def get_translations():
    """Returns available translations (KJV, NLT, NKJV, ESV)."""
    return [trans.value for trans in BibleTranslation]


# ----------------------------------------------------------------------
# 2. Custom Themes Endpoints
# ----------------------------------------------------------------------
@app.post("/api/custom-themes/create", response_model=CustomThemeModel, summary="Create and Activate AI Custom Theme", tags=["Custom Themes"])
def create_custom_theme(req: CustomThemeCreateRequest):
    """
    Takes user's natural language situation, uses the AI Theological Normalizer to generate title,
    theological summary, semantic anchors, and seeds, searches SQLite embeddings, and saves/activates it.
    """
    theme = theme_architect.curate_custom_theme(
        user_prompt=req.prompt,
        preferred_translation=req.preferred_translation.value
    )
    return theme


@app.get("/api/custom-themes", response_model=List[CustomThemeModel], summary="List All Custom Themes", tags=["Custom Themes"])
def list_custom_themes():
    """Returns all saved custom themes created by the user."""
    return db.get_all_custom_themes()


@app.get("/api/custom-themes/active", response_model=Optional[CustomThemeModel], summary="Get Active Custom Theme", tags=["Custom Themes"])
def get_active_custom_theme():
    """Returns the currently active custom theme if one is selected."""
    return db.get_active_custom_theme()


@app.post("/api/custom-themes/{theme_id}/activate", summary="Activate a Saved Custom Theme", tags=["Custom Themes"])
def activate_custom_theme(theme_id: int = FastPath(..., description="ID of custom theme to activate")):
    """Sets a specific saved custom theme as the active theme for the user."""
    success = db.activate_custom_theme(theme_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom theme {theme_id} not found")
    return {"status": "success", "message": f"Custom theme {theme_id} activated"}


# ----------------------------------------------------------------------
# 3. Scripture Retrieval & Dynamic Stream Endpoints
# ----------------------------------------------------------------------
@app.get("/api/verse/next", response_model=Optional[ExtendedVerseResponse], summary="Get Next Dynamic Scripture", tags=["Verses"])
def get_next_verse():
    """
    Retrieves the next active scripture:
    1. Checks if an active 7-day pinned daily anchor should be served today.
    2. If active theme is Custom, pulls next unshown verse from the custom theme vector stream.
    3. If active theme is standard (Peace, Wisdom, Faith, Grace, Provision), pulls next unshown verse.
    """
    settings = db.get_settings()
    is_pinned = False
    display_theme = settings.active_theme.value
    
    # 1. Custom Theme Stream
    if settings.active_theme == ScriptureTheme.CUSTOM:
        active_custom = db.get_active_custom_theme()
        if active_custom:
            display_theme = active_custom.title
            verse = theme_architect.get_next_custom_theme_verse(
                theme=active_custom,
                translation=settings.active_translation.value
            )
            if verse:
                is_pinned = db.is_verse_pinned(verse.id) if verse.id else False
                return ExtendedVerseResponse(
                    id=verse.id,
                    book=verse.book,
                    chapter=verse.chapter,
                    verse=verse.verse,
                    reference=verse.reference,
                    translation=verse.translation,
                    text=verse.text,
                    theme=display_theme,
                    is_pinned=is_pinned,
                    active_theme_display=display_theme
                )

    # 2. Standard Theme Queue
    verse = db.get_next_queue_verse()
    if not verse:
        verses = db.get_verses_by_theme(settings.active_theme.value, settings.active_translation.value)
        verse = verses[0] if verses else None

    if verse:
        is_pinned = db.is_verse_pinned(verse.id) if verse.id else False
        return ExtendedVerseResponse(
            id=verse.id,
            book=verse.book,
            chapter=verse.chapter,
            verse=verse.verse,
            reference=verse.reference,
            translation=verse.translation,
            text=verse.text,
            theme=display_theme,
            is_pinned=is_pinned,
            active_theme_display=display_theme
        )
    return None


@app.get("/api/verse/{verse_id}", response_model=ExtendedVerseResponse, summary="Get Verse by ID", tags=["Verses"])
def get_verse_by_id(verse_id: int = FastPath(..., description="ID of the verse")):
    """Retrieves a specific verse by its unique integer ID."""
    verse = db.get_verse_by_id(verse_id)
    if not verse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verse with ID {verse_id} not found")
    is_pinned = db.is_verse_pinned(verse_id)
    return ExtendedVerseResponse(
        id=verse.id,
        book=verse.book,
        chapter=verse.chapter,
        verse=verse.verse,
        reference=verse.reference,
        translation=verse.translation,
        text=verse.text,
        theme=verse.theme.value if hasattr(verse.theme, 'value') else str(verse.theme),
        is_pinned=is_pinned
    )


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


# ----------------------------------------------------------------------
# 4. User Settings & Preferences Endpoints
# ----------------------------------------------------------------------
@app.get("/api/settings", response_model=UserSettingsModel, summary="Get User Settings", tags=["Settings"])
def get_user_settings():
    """Returns the user's current preferences."""
    return db.get_settings()


@app.post("/api/settings", response_model=UserSettingsModel, summary="Update User Settings", tags=["Settings"])
def update_user_settings(settings: UserSettingsModel):
    """Updates user preferences (user name, interval minutes, daily limit, active theme, personal struggle context)."""
    db.update_settings(settings)
    return db.get_settings()


# ----------------------------------------------------------------------
# 5. Pinned Verses: 7-Day Cycle & Permanent Memory Archive
# ----------------------------------------------------------------------
@app.get("/api/verses/pinned", response_model=List[PinnedVerseModel], summary="List All Pinned Verses", tags=["Pinned Verses"])
def list_pinned_verses(active_cycle_only: bool = Query(False, description="Filter for 7-day active cycle only")):
    """Returns the user's saved 'My Verses' archive (or active 7-day cycle if filtered)."""
    if active_cycle_only:
        return db.get_active_pinned_verses()
    return db.get_pinned_archive()


@app.post("/api/verses/{verse_id}/pin", summary="Pin a Verse (Start 7-Day Cycle)", tags=["Pinned Verses"])
def pin_verse(
    verse_id: int = FastPath(..., description="Verse ID to pin"),
    notes: Optional[str] = Query(None, description="Optional personal reflection note")
):
    """Pins a verse into active 7-day rotation and saves it permanently in the archive."""
    success = db.pin_verse(verse_id, notes)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verse not found")
    return {"status": "success", "message": f"Verse {verse_id} pinned for 7-day rotation", "verse_id": verse_id, "is_pinned": True}


@app.post("/api/verses/{verse_id}/unpin", summary="Unpin a Verse", tags=["Pinned Verses"])
@app.delete("/api/verses/{verse_id}/pin", summary="Unpin a Verse", tags=["Pinned Verses"])
def unpin_verse(verse_id: int = FastPath(..., description="Verse ID to unpin")):
    """Removes a verse from pinned rotation and archive."""
    success = db.unpin_verse(verse_id)
    return {"status": "success", "message": f"Verse {verse_id} unpinned", "verse_id": verse_id, "is_pinned": False}


@app.get("/api/verses/{verse_id}/is-pinned", summary="Check if Verse is Pinned", tags=["Pinned Verses"])
def check_is_pinned(verse_id: int = FastPath(..., description="Verse ID")):
    """Returns whether a specific verse is currently pinned."""
    return {"verse_id": verse_id, "is_pinned": db.is_verse_pinned(verse_id)}


def run_server():
    """Runs the FastAPI server via uvicorn."""
    import uvicorn
    uvicorn.run(app, host=config.api_host, port=config.api_port)


if __name__ == "__main__":
    run_server()

