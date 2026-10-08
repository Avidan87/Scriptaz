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
    UserSettingsModel
)
from core.db import db
from engine.bedrock_engine import bedrock_engine
from fastapi.testclient import TestClient
from engine.api import app


def test_all_endpoints():
    print(f"\n{'='*70}\n[RUNNING FULL FASTAPI ENDPOINT VERIFICATION SUITE (v2.0)]\n{'='*70}")

    client = TestClient(app)

    # Snapshot state we mutate so the test never pollutes the real DB.
    original_settings = db.get_settings()
    existing_theme_ids = {t.id for t in db.get_all_custom_themes()}
    
    # 1. System Health
    res = client.get("/api/health")
    assert res.status_code == 200
    print(f"1.  ✅ GET /api/health -> Status: {res.json()['status']}, Verses: {res.json()['database_verse_count']}")

    # 2. 5 Themes
    res = client.get("/api/themes")
    assert res.status_code == 200
    themes = res.json()
    assert len(themes) == 5
    assert "Peace" in themes and "Wisdom" in themes and "Faith" in themes and "Grace" in themes and "Provision" in themes
    print(f"2.  ✅ GET /api/themes -> 5 Flagship Themes: {themes}")

    # 3. Translations
    res = client.get("/api/translations")
    assert res.status_code == 200
    print(f"3.  ✅ GET /api/translations -> {res.json()}")

    # 4. Next Scripture
    res = client.get("/api/verse/next")
    assert res.status_code == 200
    verse_data = res.json()
    assert verse_data is not None
    assert "is_pinned" in verse_data
    print(f"4.  ✅ GET /api/verse/next -> [{verse_data['reference']} ({verse_data['translation']})] is_pinned={verse_data['is_pinned']}")

    # 5. Verse by ID
    v_id = verse_data["id"]
    res = client.get(f"/api/verse/{v_id}")
    assert res.status_code == 200
    assert res.json()["id"] == v_id
    print(f"5.  ✅ GET /api/verse/{v_id} -> Found [{res.json()['reference']}]")

    # 6. Verses by Theme
    res = client.get("/api/verses/by-theme?theme=Wisdom&translation=NKJV&limit=3")
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
        "active_translation": "NKJV",
        "active_theme": "Peace",
        "personal_context": "Planning technical architecture",
        "launch_on_startup": False,
        "dark_mode": True
    }
    res = client.post("/api/settings", json=settings_payload)
    assert res.status_code == 200
    assert res.json()["user_name"] == "Avidan"
    assert res.json()["interval_minutes"] == 45
    print(f"8.  ✅ POST /api/settings -> Updated for user '{res.json()['user_name']}', Theme='{res.json()['active_theme']}'")

    # 9. Pin & Unpin Lifecycle (7-day cycle)
    res = client.post(f"/api/verses/{v_id}/pin?notes=Test%20Pin")
    assert res.status_code == 200
    assert res.json()["is_pinned"] is True
    print(f"9.  ✅ POST /api/verses/{v_id}/pin -> Pinned for 7-day rotation")

    res = client.get(f"/api/verses/{v_id}/is-pinned")
    assert res.status_code == 200
    assert res.json()["is_pinned"] is True
    print(f"10. ✅ GET /api/verses/{v_id}/is-pinned -> Verified is_pinned=True")

    res = client.get("/api/verses/pinned")
    assert res.status_code == 200
    assert len(res.json()) > 0
    print(f"11. ✅ GET /api/verses/pinned -> Total pinned in archive: {len(res.json())}")

    res = client.delete(f"/api/verses/{v_id}/pin")
    assert res.status_code == 200
    print(f"12. ✅ DELETE /api/verses/{v_id}/pin -> Unpinned successfully")

    # 10. Custom Themes API
    custom_theme_payload = {
        "prompt": "Dealing with workplace conflict and seeking wisdom",
        "preferred_translation": "NKJV"
    }
    res = client.post("/api/custom-themes/create", json=custom_theme_payload)
    assert res.status_code == 200
    custom_data = res.json()
    assert "title" in custom_data
    assert len(custom_data["semantic_anchors"]) > 0
    created_theme_id = custom_data.get("id")
    print(f"13. ✅ POST /api/custom-themes/create -> Curated: '{custom_data['title']}' (id={created_theme_id})")

    res = client.get("/api/custom-themes")
    assert res.status_code == 200
    assert len(res.json()) > 0
    print(f"14. ✅ GET /api/custom-themes -> Total custom themes: {len(res.json())}")

    # ------------------------------------------------------------------
    # CLEANUP: delete ONLY the exact theme id this run created (never touch
    # any pre-existing/real theme), then restore the user's original settings.
    # Bulletproof: keyed on the created id, and double-guarded so it can never
    # delete a theme that existed before the test started.
    # ------------------------------------------------------------------
    if created_theme_id is not None and created_theme_id not in existing_theme_ids:
        db.clear_journey(f"custom:{created_theme_id}")
        db.delete_custom_theme(created_theme_id)
    db.update_settings(original_settings)
    print("15. ✅ CLEANUP -> Test-created theme removed, settings restored")

    print(f"{'='*70}\n🎉 ALL ENDPOINT TESTS PASSED WITH 100% SUCCESS!\n{'='*70}\n")


if __name__ == "__main__":
    test_all_endpoints()
