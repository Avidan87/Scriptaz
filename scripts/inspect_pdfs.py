"""
Diagnostic script to inspect page counts, structure, and text extraction
from the 4 Bible translation PDFs in Scriptures/
"""

import os
from pathlib import Path
from pypdf import PdfReader

SCRIPTURES_DIR = Path("/Users/Avidan/Scriptaz/Scriptures")

PDF_FILES = {
    "KJV": "PDF-King-James-Bible.pdf",
    "NLT": "New-Living-Translation-NLT.pdf",
    "NKJV": "new-king-james-version-en.pdf",
    "ESV": "272774876-The-Holy-Bible-ESV.pdf"
}

def inspect_pdf(name: str, filename: str):
    filepath = SCRIPTURES_DIR / filename
    print(f"\n{'='*70}\n[INSPECTING {name}] => {filename}\n{'='*70}")
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return

    try:
        reader = PdfReader(str(filepath))
        total_pages = len(reader.pages)
        print(f"Total Pages: {total_pages}")

        # Sample first page with text, a middle page, and a New Testament page
        sample_indices = [min(5, total_pages - 1), total_pages // 2, min(total_pages - 20, total_pages // 2 + 200)]
        
        for idx in sample_indices:
            page = reader.pages[idx]
            text = page.extract_text() or ""
            preview = "\n".join(text.strip().splitlines()[:15])
            print(f"\n--- Page {idx+1} Preview ---")
            print(preview)
            print("--- (truncated) ---")
    except Exception as e:
        print(f"Error inspecting {name}: {e}")

if __name__ == "__main__":
    for name, filename in PDF_FILES.items():
        inspect_pdf(name, filename)
