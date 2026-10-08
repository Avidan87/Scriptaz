"""
Scriptaz — One-Time Preset Journey Builder
==========================================
Builds the teaching JOURNEY (ordered arc) for each of the 5 preset themes.
Preset themes are identical for every user, so their journeys are computed ONCE
here and shared by everyone (same pattern as the passage map / theme index).

Custom-theme journeys are built on the fly at curate time — this script is only
for the 5 presets. Safe to re-run; each rebuild replaces that theme's journey.

Run:  python scripts/build_preset_journeys.py
      python scripts/build_preset_journeys.py --only Peace,Wisdom
"""

import sys
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.models import ScriptureTheme  # noqa: E402
from engine.journey_architect import journey_architect  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=str, default="", help="Comma list of preset names to (re)build.")
    args = ap.parse_args()

    presets = [t.value for t in ScriptureTheme if t != ScriptureTheme.CUSTOM]
    if args.only:
        wanted = {n.strip().lower() for n in args.only.split(",")}
        presets = [p for p in presets if p.lower() in wanted]

    print(f"Building preset journeys for: {presets}")
    for name in presets:
        n = journey_architect.build_journey_for_preset(name)
        print(f"  {name}: {n} stages")
    print("Done.")


if __name__ == "__main__":
    main()
