"""
Comprehensive Backend, Database, and AWS Bedrock Test Suite for Scriptaz
Tests all endpoints in engine/api.py against live SQLite and Bedrock.
"""

import sys
import asyncio
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config
from core.models import (
    VerseModel,
    BibleTranslation,
    ScriptureTheme,
    UserSettingsModel,
    InsightRequest
)
from core.db import db
from engine.bedrock_engine import bedrock_engine
from fastapi.testclient import TestClient
from engine.api import app


def test_all_endpoints():
    print(f"\n{'='*70}\n[RUNNING FULL FASTAPI ENDPOINT VERIFICATION SUITE]\n{'='*70}")
    
    client = TestClient(app)
    
    # 1. System Health
    res = client.get("/api/health")
    assert res.status_code == 200
    print(f"1.  ✅ GET /api/health -> Status: {res.json()['status']}, Verses: {res.json()['database_verse_count']}")

    # 2. Themes
    res = client.get("/api/themes")
    assert res.status_code == 200
    print(f"2.  ✅ GET /api/themes -> 11 Themes: {res.json()[:4]}...")

    # 3. Translations
    res = client.get("/api/translations")
    assert res.status_code == 200
    print(f"3.  ✅ GET /api/translations -> {res.json()}")

    # 4. Next Scripture
    res = client.get("/api/verse/next")
    assert res.status_code == 200
    verse_data = res.json()
    assert verse_data is not None
    print(f"4.  ✅ GET /api/verse/next -> [{verse_data['reference']} ({verse_data['translation']})]")

    # 5. Verse by ID
    v_id = verse_data["id"]
    res = client.get(f"/api/verse/{v_id}")
    assert res.status_code == 200
    assert res.json()["id"] == v_id
    print(f"5.  ✅ GET /api/verse/{v_id} -> Found [{res.json()['reference']}]")

    # 6. Verses by Theme
    res = client.get("/api/verses/by-theme?theme=Wisdom&translation=KJV&limit=3")
    assert res.status_code == 200
    print(f"6.  ✅ GET /api/verses/by-theme (Wisdom) -> Retrieved {len(res.json())} verses")

    # 7. Multi-Translation Comparison
    res = client.get(f"/api/verses/Genesis 1:1/translations")
    assert res.status_code == 200
    print(f"7.  ✅ GET /api/verses/Genesis 1:1/translations -> Translations: {list(res.json()['translations'].keys())}")

    # 8. User Settings (GET & POST)
    settings_payload = {
        "user_name": "Avidan",
        "interval_minutes": 45,
        "daily_limit": 6,
        "active_translation": "KJV",
        "active_theme": "Wisdom",
        "personal_context": "Planning technical architecture",
        "launch_on_startup": False,
        "dark_mode": True
    }
    res = client.post("/api/settings", json=settings_payload)
    assert res.status_code == 200
    assert res.json()["user_name"] == "Avidan"
    assert res.json()["interval_minutes"] == 45
    print(f"8.  ✅ POST /api/settings -> Updated for user '{res.json()['user_name']}', Theme='{res.json()['active_theme']}'")

    res = client.get("/api/settings")
    assert res.status_code == 200
    assert res.json()["user_name"] == "Avidan"
    print(f"9.  ✅ GET /api/settings -> Confirmed user_name: '{res.json()['user_name']}'")

    # 10. Pin & Unpin
    res = client.post(f"/api/verses/{v_id}/pin?notes=Test%20Pin")
    assert res.status_code == 200
    print(f"10. ✅ POST /api/verses/{v_id}/pin -> Pinned successfully")

    res = client.get("/api/verses/pinned")
    assert res.status_code == 200
    assert len(res.json()) > 0
    print(f"11. ✅ GET /api/verses/pinned -> Total pinned in archive: {len(res.json())}")

    res = client.delete(f"/api/verses/{v_id}/pin")
    assert res.status_code == 200
    print(f"12. ✅ DELETE /api/verses/{v_id}/pin -> Unpinned successfully")

    # 13. Direct JSON Deep Insight
    insight_payload = {
        "reference": "Proverbs 3:5-6",
        "translation": "KJV",
        "verse_text": "Trust in the LORD with all thine heart; and lean not unto thine own understanding.",
        "active_theme": "Wisdom",
        "personal_context": "Navigating software design choices",
        "user_name": "Avidan"
    }
    print("\n⏳ Generating Deep Insight via POST /api/insight...")
    res = client.post("/api/insight", json=insight_payload)
    assert res.status_code == 200
    print(f"13. ✅ POST /api/insight -> Response received ({len(res.json()['christ_centered_revelation'])} chars)")
    print(f"\n--- Preview of Deep Insight Response ---")
    print(res.json()["christ_centered_revelation"][:250] + "...\n")

    print(f"{'='*70}\n🎉 ALL 13 ENDPOINT TESTS PASSED WITH 100% SUCCESS!\n{'='*70}\n")


if __name__ == "__main__":
    test_all_endpoints()
