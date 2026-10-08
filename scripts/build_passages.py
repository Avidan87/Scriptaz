"""
Scriptaz — Intelligent Passage Segmentation Builder (LLM + validated fallback)
=============================================================================
Computes, ONCE and offline, the natural passage unit each verse belongs to, so the
app can decide when a verse must be shown with its connected neighbours (context)
versus standing alone — all resolved at delivery time by a cheap local lookup.

WHY LLM, not punctuation:
  The old approach guessed sense-units from punctuation ("does it end in a full
  stop"). Syntax is a poor proxy for meaning — it over-joins and it fractures
  run-on sentences. Here a language model reads each chapter and groups verses by
  the only test that matters: *could a reader understand this passage on its own,
  with zero outside context?* The model runs ONCE, offline; delivery stays instant
  and network-free (it just reads verse_passage_map).

SAFETY (never worse than before):
  * Every chapter also gets the deterministic grammar heuristic as a fallback.
  * The model's grouping is accepted ONLY if it passes strict CODE validation:
    it must be an in-order partition of exactly the verse numbers we sent it (no
    invented numbers, none dropped, none duplicated) with no group over HARD_CAP.
  * Any chapter that fails validation (or errors) silently uses the heuristic.
  * Translation-specific verse gaps (e.g. Mark 9:44 absent in ESV) are annotated
    inline so the model never miscounts around them.

Run:
  python scripts/build_passages.py                # full rebuild, all translations
  python scripts/build_passages.py --heuristic    # no LLM, deterministic only (old behaviour)
  python scripts/build_passages.py --limit 30     # LLM on first 30 chapters (smoke test)
  python scripts/build_passages.py --sample "ESV:Mark:9,KJV:Ephesians:1"  # specific chapters, prints before/after
  python scripts/build_passages.py --workers 16   # concurrency (default 12)
"""

import sys
import re
import argparse
import time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config  # noqa: E402
from core.db import db  # noqa: E402
from engine.bedrock_engine import bedrock_engine  # noqa: E402

# ----------------------------------------------------------------------
# Tuning knobs
# ----------------------------------------------------------------------
TARGET_LEN = 5
HARD_CAP = 7
WISDOM_SINGLETON_BOOKS = {"Proverbs", "Ecclesiastes"}
DEFAULT_WORKERS = 12
LLM_RETRIES = 3

DEPENDENT_OPENERS = {
    "therefore", "for", "because", "so", "wherefore", "which", "thus",
    "since", "hence", "whereby", "thereby", "thereof", "whereupon", "wherein",
}
_TRAILING_STRIP = ' \t"\'”’)]'

SEGMENT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}},
        }
    },
    "required": ["groups"],
}

SYSTEM_PROMPT = (
    "You are segmenting a Bible chapter into passages for a devotional app. A passage "
    "is a group of one or more consecutive verses that a reader could understand with "
    "ZERO outside context — that is the only test that matters, not punctuation or "
    "sentence length. Prefer the SHORTEST grouping that still stands on its own; a "
    "single verse alone is the default, and you should only join verses when splitting "
    "them would leave one part not making sense by itself. Aim for about {target} "
    "verses when a thought genuinely runs that long; never put more than {cap} verses "
    "in one group.{wisdom} Some verse numbers may be intentionally absent from this "
    "translation — the numbers given are complete and final, so do not infer or insert "
    "missing numbers. Call segment_passages with 'groups': an in-order list of groups, "
    "each group an explicit list of the real verse numbers in it. Together the groups "
    "must cover every verse number you were given, each exactly once, in order — invent "
    "no number, drop no number."
)
WISDOM_CLAUSE = (
    " This is a wisdom book — each verse is typically a self-contained proverb, so "
    "strongly favour single-verse groups."
)


# ----------------------------------------------------------------------
# Deterministic heuristic (validated fallback — the previous behaviour)
# ----------------------------------------------------------------------
def ends_sentence(text: str) -> bool:
    t = (text or "").rstrip(_TRAILING_STRIP)
    return bool(t) and t[-1] in ".!?"


def starts_dependent(text: str) -> bool:
    t = (text or "").lstrip(' \t"\'“‘([')
    if not t:
        return False
    if t[0].islower():
        return True
    first_word = re.split(r"[\s,;:.]", t, 1)[0].lower()
    return first_word in DEPENDENT_OPENERS


def starts_lowercase(text: str) -> bool:
    t = (text or "").lstrip(' \t"\'“‘([')
    return bool(t) and t[0].islower()


def heuristic_segment(verses, is_wisdom: bool):
    """verses: ordered [(vnum, text)] -> dict vnum -> (start, end)."""
    n = len(verses)
    nums = [v for v, _ in verses]
    texts = {v: t for v, t in verses}

    def forced_join(i_num, j_num) -> bool:
        return (not ends_sentence(texts[i_num])) or starts_lowercase(texts[j_num])

    def logical_join(i_num, j_num) -> bool:
        if is_wisdom:
            return False
        return ends_sentence(texts[i_num]) and starts_dependent(texts[j_num])

    result = {}
    idx = 0
    while idx < n:
        start = nums[idx]
        end = start
        e_idx = idx
        while e_idx + 1 < n:
            cur, nxt = nums[e_idx], nums[e_idx + 1]
            length = (e_idx - idx) + 1
            if forced_join(cur, nxt):
                if length >= HARD_CAP:
                    break
                e_idx += 1
                end = nxt
                continue
            if logical_join(cur, nxt) and length < TARGET_LEN:
                e_idx += 1
                end = nxt
                continue
            break
        if not ends_sentence(texts[end]):
            back = e_idx
            while back > idx and not ends_sentence(texts[nums[back]]):
                back -= 1
            if ends_sentence(texts[nums[back]]):
                e_idx = back
                end = nums[back]
        for k in range(idx, e_idx + 1):
            result[nums[k]] = (start, end)
        idx = e_idx + 1
    return result


# ----------------------------------------------------------------------
# LLM segmentation
# ----------------------------------------------------------------------
def build_numbered_text(verses) -> str:
    """Numbered chapter text with explicit gap annotations for absent verse numbers."""
    lines = []
    nums = [v for v, _ in verses]
    present = set(nums)
    texts = {v: t for v, t in verses}
    for i, v in enumerate(nums):
        lines.append(f"{v}: {texts[v]}")
        if i + 1 < len(nums):
            nxt = nums[i + 1]
            for missing in range(v + 1, nxt):
                if missing not in present:
                    lines.append(f"[verse {missing} does not exist in this translation]")
    return "\n".join(lines)


def validate_groups(groups, present_nums) -> bool:
    """Accept only an in-order partition of exactly the present verse numbers,
    with no group exceeding HARD_CAP present verses."""
    if not isinstance(groups, list) or not groups:
        return False
    flat = []
    for g in groups:
        if not isinstance(g, list) or not g:
            return False
        if len(g) > HARD_CAP:
            return False
        flat.extend(g)
    # Exact same numbers, each once, and in the same order we supplied.
    return flat == list(present_nums)


def groups_to_spans(groups):
    spans = {}
    for g in groups:
        s, e = min(g), max(g)
        for v in g:
            spans[v] = (s, e)
    return spans


def llm_segment(book, chapter, verses, is_wisdom):
    """Returns (spans_dict, 'llm') on success, else (None, reason).

    NOTE: no blanket wisdom-book bias here. The model applies the same 'stand
    alone with zero context' test everywhere — which naturally makes true
    aphorisms (Proverbs 10+) singletons while keeping connected discourse
    (Proverbs 1-9 'My son...') together. The wisdom prior lives only in the
    deterministic heuristic fallback, which cannot reason for itself.
    """
    nums = [v for v, _ in verses]
    system = SYSTEM_PROMPT.format(target=TARGET_LEN, cap=HARD_CAP, wisdom="")
    user_text = f"{book} {chapter}\n\n{build_numbered_text(verses)}"
    for attempt in range(LLM_RETRIES):
        result = bedrock_engine.converse_tool(
            user_text=user_text,
            tool_name="segment_passages",
            tool_schema=SEGMENT_TOOL_SCHEMA,
            system_prompt=system,
            tool_description="Group the chapter's verses into stand-alone passages.",
            max_tokens=1500,
            temperature=0.0,
        )
        if result and "groups" in result and validate_groups(result["groups"], nums):
            return groups_to_spans(result["groups"]), "llm"
        time.sleep(0.6 * (attempt + 1))  # brief backoff before retry
    return None, "invalid"


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------
def load_chapters(trans_filter=None):
    """Returns dict (trans, book, chapter) -> ordered [(vnum, text)]."""
    chapters = {}
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT translation FROM verses ORDER BY translation;")
        translations = [r["translation"] for r in cur.fetchall()]
        for trans in translations:
            if trans_filter and trans not in trans_filter:
                continue
            cur.execute(
                "SELECT book, chapter, verse, text FROM verses WHERE translation = ? ORDER BY book, chapter, verse",
                (trans,),
            )
            for r in cur.fetchall():
                chapters.setdefault((trans, r["book"], r["chapter"]), []).append((r["verse"], r["text"]))
    for key in chapters:
        chapters[key].sort(key=lambda x: x[0])
    return chapters


def segment_one(job):
    """Worker: compute spans for one chapter. LLM with heuristic fallback."""
    trans, book, chapter, verses, use_llm = job
    is_wisdom = book in WISDOM_SINGLETON_BOOKS
    heuristic = heuristic_segment(verses, is_wisdom)
    if not use_llm:
        return (trans, book, chapter, heuristic, "heuristic")
    spans, reason = llm_segment(book, chapter, verses, is_wisdom)
    if spans is None:
        return (trans, book, chapter, heuristic, f"fallback:{reason}")
    return (trans, book, chapter, spans, "llm")


def write_chapter(cur, trans, book, chapter, spans):
    cur.execute(
        "DELETE FROM verse_passage_map WHERE translation=? AND book=? AND chapter=?",
        (trans, book, chapter),
    )
    cur.executemany(
        "INSERT INTO verse_passage_map (translation, book, chapter, verse, start_verse, end_verse) VALUES (?,?,?,?,?,?)",
        [(trans, book, chapter, v, s, e) for v, (s, e) in spans.items()],
    )


def ensure_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS verse_passage_map (
            translation TEXT NOT NULL, book TEXT NOT NULL, chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL, start_verse INTEGER NOT NULL, end_verse INTEGER NOT NULL,
            PRIMARY KEY (translation, book, chapter, verse)
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_passage_lookup ON verse_passage_map(translation, book, chapter, verse);")


def spans_to_passages(spans):
    """Distinct (start,end) passages in a chapter's span map."""
    return sorted(set(spans.values()))


def print_before_after(trans, book, chapter, verses, old_spans, new_spans):
    texts = {v: t for v, t in verses}
    print(f"\n── {trans} {book} {chapter} ──")
    for label, spans in (("OLD", old_spans), ("NEW", new_spans)):
        print(f"  {label}:")
        for s, e in spans_to_passages(spans):
            body = " ".join(texts.get(v, "") for v in range(s, e + 1) if v in texts)
            rng = f"{s}" if s == e else f"{s}-{e}"
            print(f"    v{rng}: {body[:110]}{'…' if len(body) > 110 else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heuristic", action="store_true", help="Deterministic only, no LLM.")
    ap.add_argument("--limit", type=int, default=0, help="LLM on first N chapters only (smoke test).")
    ap.add_argument("--sample", type=str, default="", help="Comma list of TRANS:Book:Chapter; prints before/after.")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = ap.parse_args()

    use_llm = not args.heuristic
    sample_keys = set()
    trans_filter = None
    if args.sample:
        for tok in args.sample.split(","):
            parts = tok.split(":")
            if len(parts) == 3:
                sample_keys.add((parts[0].strip(), parts[1].strip(), int(parts[2])))
        trans_filter = {k[0] for k in sample_keys}

    print(f"Building passage map -> {config.db_path}")
    print(f"Mode: {'HEURISTIC' if not use_llm else 'LLM+fallback'} | workers={args.workers}"
          + (f" | limit={args.limit}" if args.limit else "")
          + (f" | sample={len(sample_keys)} chapters" if sample_keys else ""))

    chapters = load_chapters(trans_filter)
    keys = list(chapters.keys())
    if sample_keys:
        keys = [k for k in keys if k in sample_keys]
    keys.sort()

    # Capture OLD spans (for sample before/after) before we overwrite.
    old_map = {}
    if sample_keys:
        for k in keys:
            trans, book, chapter = k
            old_map[k] = heuristic_segment(chapters[k], book in WISDOM_SINGLETON_BOOKS)
            with db._get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute(
                        "SELECT verse, start_verse, end_verse FROM verse_passage_map WHERE translation=? AND book=? AND chapter=?",
                        (trans, book, chapter),
                    )
                    rows = cur.fetchall()
                    if rows:
                        old_map[k] = {r["verse"]: (r["start_verse"], r["end_verse"]) for r in rows}
                except Exception:
                    pass

    jobs = []
    for i, k in enumerate(keys):
        trans, book, chapter = k
        chapter_use_llm = use_llm and (not args.limit or i < args.limit)
        jobs.append((trans, book, chapter, chapters[k], chapter_use_llm))

    results = []
    stats = defaultdict(lambda: defaultdict(int))  # trans -> {llm, heuristic, fallback}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(segment_one, j): j for j in jobs}
        done = 0
        for fut in as_completed(futs):
            trans, book, chapter, spans, source = fut.result()
            results.append((trans, book, chapter, spans, source))
            bucket = "llm" if source == "llm" else ("heuristic" if source == "heuristic" else "fallback")
            stats[trans][bucket] += 1
            done += 1
            if done % 100 == 0 or done == len(jobs):
                print(f"  ...{done}/{len(jobs)} chapters ({time.time()-t0:.0f}s)")

    # Single-writer commit (avoids cross-thread sqlite contention).
    with db._get_connection() as conn:
        cur = conn.cursor()
        ensure_table(cur)
        for trans, book, chapter, spans, _ in results:
            write_chapter(cur, trans, book, chapter, spans)
        conn.commit()

    # Report
    total_rows = sum(len(s) for _, _, _, s, _ in results)
    total_passages = 0
    multi = 0
    for _, _, _, spans, _ in results:
        for s, e in spans_to_passages(spans):
            total_passages += 1
            if e > s:
                multi += 1
    pct = (multi / total_passages * 100) if total_passages else 0

    print("\n=== Segmentation summary ===")
    for trans in sorted(stats):
        s = stats[trans]
        tot = s["llm"] + s["heuristic"] + s["fallback"]
        print(f"  {trans}: {tot:>4} chapters — {s['llm']} LLM, {s['fallback']} fallback, {s['heuristic']} heuristic-only")
    print(f"\nDone in {time.time()-t0:.0f}s. {total_rows} verses -> {total_passages} passages "
          f"({multi} multi-verse, {pct:.1f}%).")

    if sample_keys:
        print("\n=== BEFORE / AFTER (sampled chapters) ===")
        res_by_key = {(t, b, c): sp for t, b, c, sp, _ in results}
        for k in keys:
            if k in res_by_key:
                print_before_after(k[0], k[1], k[2], chapters[k], old_map.get(k, {}), res_by_key[k])


if __name__ == "__main__":
    main()
