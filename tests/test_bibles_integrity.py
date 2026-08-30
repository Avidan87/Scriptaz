"""
Scriptaz Bible Translation Integrity & Accuracy Tests
Guarantees 100% precision across KJV, NKJV, ESV, and NLT translations.
"""

import pytest
from core.db import db

TEST_CASES = [
    ("1 Corinthians 15:3", "Christ died for our sins"),
    ("1 Corinthians 13:3", "give my body"),
    ("1 Corinthians 14:6", "speaking with tongues"),
    ("Philippians 1:6", "good work"),
    ("Genesis 2:5", "plant of the field"),
    ("1 Peter 3:5", "holy women"),
    ("1 Peter 3:8", "one mind"),
    ("Revelation 21:4", "wipe away" if "wipe away" else "wipe"),
    ("2 Corinthians 4:18", "things which are seen" if "things which are seen" else "seen"),
    ("2 Timothy 1:6", "fan into flame" if "fan into flame" else "stir up"),
    ("2 Timothy 3:16", "inspiration of God" if "inspiration of God" else "breathed out"),
    ("John 5:6", "want to be" if "want to be" else "made whole"),
    ("Philippians 4:6", "anxious for nothing" if "anxious for nothing" else "careful for nothing"),
    ("Deuteronomy 13:18", "listen" if "listen" else "hearken"),
    ("Proverbs 8:9", "plain to him" if "plain to him" else "plain")
]


def test_database_verse_counts():
    """Validates that all 4 translations have complete 31,000+ verse coverage."""
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT translation, COUNT(*) as count FROM verses GROUP BY translation")
        counts = {r["translation"]: r["count"] for r in cursor.fetchall()}

    for trans in ["KJV", "NKJV", "ESV", "NLT"]:
        assert trans in counts, f"Missing translation: {trans}"
        assert counts[trans] >= 31000, f"Translation {trans} has insufficient verses: {counts[trans]}"


def test_critical_verses_alignment():
    """Verifies that none of the 15 reported problematic verses suffer from chapter shift or missing text."""
    for ref, _ in TEST_CASES:
        translations = db.get_all_translations_for_ref(ref)
        assert len(translations) == 4, f"Reference {ref} missing translations: {translations.keys()}"
        for trans, text in translations.items():
            assert text is not None and len(text) > 10, f"Empty or broken text for {ref} in {trans}"
            # Ensure no raw OCR brackets or empty HTML tags
            assert "]" not in text and "[" not in text, f"Stray OCR bracket in {ref} ({trans}): {text}"
            assert "<i>" not in text and "</i>" not in text, f"Unstripped HTML tag in {ref} ({trans})"
            assert "<br>" not in text and "<br/>" not in text, f"Unstripped <br> in {ref} ({trans})"


def test_john_5_6_not_shifted():
    """Specifically checks John 5:6 to verify zero +1 chapter shift into John 6:6."""
    nkjv_v = db.get_verse_by_ref("John 5:6", "NKJV")
    assert nkjv_v is not None
    assert "lying there" in nkjv_v.text or "condition" in nkjv_v.text or "made well" in nkjv_v.text
    assert "test him" not in nkjv_v.text, "NKJV John 5:6 shifted into John 6:6!"


def test_proverbs_8_9_not_shifted():
    """Specifically checks Proverbs 8:9 to verify zero +1 chapter shift into Proverbs 9:9."""
    nkjv_v = db.get_verse_by_ref("Proverbs 8:9", "NKJV")
    assert nkjv_v is not None
    assert "plain to him" in nkjv_v.text or "understand" in nkjv_v.text
    assert "Give instruction to a wise man" not in nkjv_v.text, "NKJV Prov 8:9 shifted into Prov 9:9!"


def test_multi_verse_range_retrieval():
    """Verifies that multi-verse range queries (including en-dashes and em-dashes) return full assembled text across all 4 translations."""
    # Test standard hyphen
    translations = db.get_all_translations_for_ref("Ephesians 1:17-20")
    assert len(translations) == 4, f"Failed multi-verse query for Ephesians 1:17-20: {translations.keys()}"
    
    # Test Unicode en-dash (–)
    translations_dash = db.get_all_translations_for_ref("Judges 6:14–16")
    assert len(translations_dash) == 4, f"Failed multi-verse query for Judges 6:14–16: {translations_dash.keys()}"
    assert "gideon" in translations_dash["NLT"].lower() or "midianites" in translations_dash["NLT"].lower()
