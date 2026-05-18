"""
demo_runner.py — Interactive terminal walkthrough of the inverted index.

TWO MODES (chosen from main menu):
────────────────────────────────────────────────────────────────────
MODE 1: Generate a Worksheet
    Walks through the full 8-stage pipeline:
    STAGE 0  load/build index from disk
    STAGE 1  pick curriculum level (O-Level / A-Level)
    STAGE 2  pick subject (filtered by level)
    STAGE 3a pick tier (AS / A2) — A-Level only
    STAGE 3b pick paper style (MCQ / Theory)
    STAGE 4  pick topics (filtered by tier)
    STAGE 5  pick year range
    STAGE 6  run the inverted index (query → union → fetch)
    STAGE 7  select questions (Fisher-Yates shuffle + greedy fill)
    STAGE 8  compile and save the PDF worksheet

MODE 2: Data Structure Operations Demo
    Interactive menu showing each InvertedIndex class method in isolation:
    [1] INSERT       index.insert(key, record)
    [2] SEARCH       index.query(key)           ← O(1) hash lookup
    [3] UNION        index.union([keys])
    [4] INTERSECT    index.intersect([keys])
    [5] DELETE       index.remove_question(qid)
    [6] VIEW TREE    index.view_tree()
    [7] BENCHMARK    index.query() vs naive O(n) scan

Run from project root:
    python demo_runner.py
"""
import random
import os
import sys
import time
import json
from typing import Any, Callable, Dict, List, Optional

from config import (
    A_LEVEL_SUBJECTS, INDEX_PATH, KEYWORD_MAP_PATH,
    O_LEVEL_SUBJECTS, OUTPUT_DIR, SUBJECTS,
)
from inverted_index import InvertedIndex
from build_index import build_master_index
from worksheet_generator import generate_worksheet


# ════════════════════════════════════════════════════════════════════
# UI HELPERS
# Small formatting functions used throughout both modes.
# ════════════════════════════════════════════════════════════════════
RULE = "─" * 72
SECTION = "═" * 72


def banner(text: str) -> None:
    """Print a thick-bordered banner — used at program start and end."""
    print()
    print(SECTION)
    print(f"  {text}")
    print(SECTION)


def section(text: str) -> None:
    """Print a thin-bordered section header — used before each stage."""
    print()
    print(RULE)
    print(f"  {text}")
    print(RULE)


def info(text: str) -> None:
    """Print an indented bullet line — used for explanatory messages."""
    print(f"  ▸ {text}")


def kv(label: str, value: Any) -> None:
    """Print a key-value pair — used to display stats and results."""
    print(f"    • {label:<22} {value}")


def show_keys(keys: List[str], index: InvertedIndex, max_show: int = 8) -> None:
    """Print composite keys with their postings counts — used in STAGE 6."""
    print(f"    composite keys ({len(keys)}):")
    for k in keys[:max_show]:
        n = len(index.query(k))
        print(f"        {k:<55s}  postings={n}")
    if len(keys) > max_show:
        print(f"        ... and {len(keys) - max_show} more")


def ask_choice(
    prompt: str,
    options: List[str],
    labeller: Optional[Callable[[str], str]] = None,
    allow_back: bool = False,
) -> Optional[str]:
    """
    Show numbered options, read a single choice, return the selected value.
    If allow_back=True, user can type 'b' to return None (go back).
    """
    if not options:
        info("(no options available — returning)")
        return None
    print()
    for i, opt in enumerate(options, start=1):
        label = labeller(opt) if labeller else opt
        print(f"    [{i}]  {label}")
    if allow_back:
        print(f"    [b]  back")
    while True:
        try:
            raw = input(f"\n  {prompt} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if allow_back and raw == "b":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"    invalid — pick a number 1–{len(options)}"
              + (" or 'b'" if allow_back else ""))


def ask_multi(
    prompt: str,
    options: List[str],
    min_one: bool = True,
) -> List[str]:
    """
    Show numbered options, read comma-separated choices or 'all'.
    Returns a list of selected values.
    Used in STAGE 4 (topic selection).
    """
    if not options:
        return []
    print()
    for i, opt in enumerate(options, start=1):
        print(f"    [{i:>2}]  {opt}")
    print("    [all] select every option")
    while True:
        try:
            raw = input(f"\n  {prompt} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if raw == "all":
            return list(options)
        try:
            picks = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            print("    invalid — use comma-separated numbers, e.g. 1,3,5")
            continue
        if not picks and min_one:
            print("    pick at least one")
            continue
        if any(p < 1 or p > len(options) for p in picks):
            print(f"    out of range — must be 1–{len(options)}")
            continue
        return [options[p - 1] for p in picks]


def ask_int(prompt: str, default: int, lo: int = 0, hi: int = 9999) -> int:
    """Read an integer from the user with a default fallback."""
    while True:
        try:
            raw = input(f"  {prompt} [default {default}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if not raw:
            return default
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"    please enter a number between {lo} and {hi}")


# ════════════════════════════════════════════════════════════════════
# MODE 1 — WORKSHEET GENERATION
# These functions implement the 8-stage worksheet generation pipeline.
# They are ONLY called when the user picks "Generate a Worksheet".
# ════════════════════════════════════════════════════════════════════

def load_or_build_index() -> InvertedIndex:
    """
    STAGE 0 — Load the inverted index from disk if cached, else build it.

    Calls:
        index.load(path)   — JSON deserialisation into main_index + question_store
        build_master_index — ingests PDFs, tags topics, builds and saves the index
    """
    index = InvertedIndex(keyword_map_path=KEYWORD_MAP_PATH)

    if os.path.exists(INDEX_PATH):
        section("STAGE 0  ·  Loading cached inverted index")
        info(f"reading {INDEX_PATH}")
        t0 = time.perf_counter()
        index.load(INDEX_PATH)
        dt = (time.perf_counter() - t0) * 1000
        info(f"loaded in {dt:.1f} ms")
        s = index.stats()
        kv("keys",      s["n_keys"])
        kv("questions", s["n_questions"])
        kv("subjects",  s["n_subjects"])
        kv("avg postings/key", s["avg_postings"])
        return index

    section("STAGE 0  ·  No cached index — building from PDFs")
    info("running ingestion (this may take a moment)")
    index = build_master_index("data/papers/qp", KEYWORD_MAP_PATH)
    return index

def pick_level() -> str:
    """STAGE 1 — Ask the user to choose O-Level or A-Level."""
    section("STAGE 1  ·  Pick a curriculum level")
    info("This filters which subject codes you can pick next.")
    info("O-Level = pure-syllabus papers; A-Level = AS / A2 split.")
    return ask_choice("level: ", ["O-Level", "A-Level"])

def pick_subject(index: InvertedIndex, level: str) -> Optional[str]:
    """
    STAGE 2 — Show subjects present in the index filtered by level.

    Calls:
        index.list_subjects() — peels the subject prefix off every key in main_index
    """
    section("STAGE 2  ·  Pick a subject")

    available = index.list_subjects()
    info(f"index.list_subjects() → {available}")
    info("(this walks every key in main_index and peels off the subject prefix)")


    #----- target_set contains subjects that belongs to either A level or O level
    target_set = O_LEVEL_SUBJECTS if level == "O-Level" else A_LEVEL_SUBJECTS
    #----- candidates contains subjects that are in target set AND the inverted_index instance
    candidates = [s for s in available if s in target_set]

    if not candidates:
        print()
        info(f"no {level} subjects available in the index — try the another curriculum level")
        return None

    chosen = ask_choice(
        "subject: ",
        candidates,
        labeller=lambda code: f"{SUBJECTS.get(code, code)}  ({code})",
        allow_back=True,
    )
    return chosen


def pick_tier(level : str) -> str:
    """
    STAGE 3a — For A-Level, ask AS or A2. For O-Level, return 'ALL'.

    The tier determines:
      - which topics are shown (AS topics vs A2 topics from keyword_map)
      - which paper variants are searched (p1x/p2x vs p4x/p5x)
    """
    section("STAGE 3a  ·  Pick a tier  (A-Level only)")
    
    if (level not in ["A-Level", "O-Level"]): #exception handling for incorrect input
        return None
    
    if level == "O-Level":
        return "ALL"
    else:
        info("AS  = first year (papers 1x, 2x, 3x)")
        info("A2  = second year (papers 4x, 5x)")
        
        tier = ask_choice(
            "tier: ",
            ["AS", "A2"],
            labeller=lambda t: {
                "AS":   "AS   — first year papers (p1x, p2x, p3x)",
                "A2":   "A2   — second year papers (p4x, p5x)",
            }.get(t, t),
        )
        return tier


def pick_paper_style() -> str:
    """
    STAGE 3b — Ask MCQ or Theory.

    Prevents mixing 1-mark A/B/C/D MCQ questions with multi-part
    structured questions in the same worksheet.
    """
    section("STAGE 3b  ·  Pick a paper style")
    info("MCQ    = multiple choice questions (Paper 1, 1 mark each)")
    info("Theory = structured questions with diagrams (Paper 2/4)")
    style = ask_choice(
        "style: ",
        ["MCQ", "Theory"],
        labeller=lambda s: {
            "MCQ":    "MCQ    — multiple choice (Paper 1)",
            "Theory": "Theory — structured questions (Paper 2/4)",
        }.get(s, s),
    )
    return style


def _topics_for_tier(
    index: InvertedIndex,
    subject: str,
    tier: str,
    keyword_map: Dict[str, Any],
) -> List[str]:
    """
    Internal helper for STAGE 4.
    Returns the topics that are (a) present in the index AND
    (b) belong to the selected tier in the keyword_map.

    Calls:
        index.list_topics(subject) — scans keys to find distinct topics
    """
    all_indexed_topics = set(index.list_topics(subject))

    subj_map = keyword_map.get(subject, {})

    # Subjects with no tier split (O-Level, or A-Level "Both")
    if "ALL" in subj_map or tier == "Both":
        # Merge all tiers from the map to build the allowed set
        allowed: set = set()
        for tier_key, topic_dict in subj_map.items():
            allowed.update(topic_dict.keys())
        # Return only those actually in the index (preserve index order)
        return sorted(all_indexed_topics & allowed) if allowed else sorted(all_indexed_topics)

    # Tier-split subjects (A-Level)
    tier_topics = set(subj_map.get(tier, {}).keys())
    filtered = all_indexed_topics & tier_topics

    # Graceful fallback: if the tier filter produces nothing, show everything
    if not filtered:
        info(f"  (no '{tier}' topics found in keyword map — showing all indexed topics)")
        return sorted(all_indexed_topics)

    return sorted(filtered)


def pick_topics(
    index: InvertedIndex,
    subject: str,
    tier: str,
    keyword_map: Dict[str, Any],
) -> List[str]:
    """
    STAGE 4 — Show tier-filtered topics, let user pick one or more.

    Calls:
        index.list_topics(subject) — via _topics_for_tier
    """
    section("STAGE 4  ·  Pick topics")

    topics = _topics_for_tier(index, subject, tier, keyword_map)

    info(f"tier={tier!r} → {len(topics)} topics available for {subject}")
    info("(filtered against keyword_map tier, then cross-checked with index keys)")

    if not topics:
        info("(no topics — was anything indexed for this subject / tier?)")
        return []

    return ask_multi("pick topics (comma-separated, e.g. 1,3,5): ", topics)


def pick_year_range(index: InvertedIndex, subject: str) -> tuple:
    """
    STAGE 5 — Ask from/to year.

    Calls:
        index.list_years(subject) — scans question_store for distinct years
    """
    section("STAGE 5  ·  Pick a year range")
    years = index.list_years(subject)
    info(f"index.list_years({subject!r})  →  {years}")

    if not years:
        return 2000, 2030

    earliest, latest = years[0], years[-1]
    info(f"available range is {earliest}–{latest}")
    yfrom = ask_int("from year", earliest, 2000, 2030)
    yto   = ask_int("to year",   latest,   yfrom, 2030)
    return yfrom, yto


def _resolve_paper_variants(
    index: InvertedIndex,
    subject: str,
    tier: str,
    paper_style: str = "Theory",
) -> List[str]:
    """
    Internal helper for STAGE 6.
    Converts tier + paper_style into actual paper variant codes
    that exist in the index (e.g. ['p21', 'p22', 'p23']).

    Calls:
        index.list_paper_types(subject) — scans keys for distinct paper variants
    """
    available = index.list_paper_types(subject)
    if not available:
        return []

    # First filter by tier
    if tier == "AS":
        tier_filtered = [p for p in available if p[-1] in {"1", "2", "3"}]
    elif tier == "A2":
        tier_filtered = [p for p in available if p[-1] in {"4", "5"}]
    else:
        tier_filtered = available

    # Then filter by paper style
    if paper_style == "MCQ":
        # MCQ papers start with p1 (AS) — e.g. p11, p12, p13
        return [p for p in tier_filtered if p.startswith("p1")]
    elif paper_style == "Theory":
        # Structured papers start with p2 (AS) or p4 (A2)
        return [p for p in tier_filtered if p.startswith("p2") or p.startswith("p4")]
    return tier_filtered


def run_search(
    index: InvertedIndex,
    subject: str,
    topics: List[str],
    tier: str,
    paper_style: str,
    year_from: int,
    year_to: int,
) -> List[Dict[str, Any]]:
    """
    STAGE 6 — Run the full inverted index retrieval pipeline.

    NOTE: this is NOT the same as the isolated _demo_search in MODE 2.
    run_search is the full pipeline:
        step 6a: resolve tier+style → paper variants
        step 6b: build composite keys (topic × variant cartesian product)
        step 6c: call index.query(key) for each key — O(1) per key
        step 6d: index.union(keys) — deduplicate ids across all keys
        step 6e: index.fetch_documents() — resolve ids → records, apply year filter

    Calls:
        index.keys_for()        — builds composite key strings
        index.query()           — O(1) postings lookup per key
        index.union()           — set union across postings lists
        index.fetch_documents() — id → full record, with year filter
    """
    section("STAGE 6  ·  Run the inverted index")

    # 6a — resolve tier + style → actual paper variants
    chosen_variants = _resolve_paper_variants(index, subject, tier, paper_style)
    info(f"resolved tier {tier!r} + style {paper_style!r} → paper variants: {chosen_variants}")

    # 6b — composite keys
    keys = index.keys_for(subject, topics, chosen_variants)
    info(f"built {len(keys)} composite keys via topic × variant cross-product:")
    show_keys(keys, index)

    # 6c — query each key (this is the O(1) hash hit per key)
    print()
    info("query each key — direct dict lookup, O(1):")
    t0 = time.perf_counter()
    per_key_counts: List[int] = []
    for k in keys:
        per_key_counts.append(len(index.query(k)))
    dt_q = (time.perf_counter() - t0) * 1000
    kv("total time for all queries", f"{dt_q:.3f} ms")
    kv("total postings retrieved",   sum(per_key_counts))

    # 6d — union (set dedup)
    print()
    info("UNION — collapse postings lists across keys, deduplicating ids")
    t0 = time.perf_counter()
    candidate_ids = index.union(keys)
    dt_u = (time.perf_counter() - t0) * 1000
    kv("union time", f"{dt_u:.3f} ms")
    kv("unique candidate ids", len(candidate_ids))

    # 6e — fetch + year filter
    print()
    info("fetch_documents — resolve ids → full records, apply year filter")
    t0 = time.perf_counter()
    candidates = index.fetch_documents(candidate_ids, year_from, year_to)
    dt_f = (time.perf_counter() - t0) * 1000
    kv("fetch + filter time", f"{dt_f:.3f} ms")
    kv(f"records in [{year_from}, {year_to}]", len(candidates))

    # 6f — preview a few
    if candidates:
        print()
        info("first few candidates:")
        for c in candidates[:5]:
            topics_str = ", ".join(c.get("topic", []))[:36]
            print(f"        {c['id']:<35s}  "
                  f"y={c['year']}  "
                  f"marks={c['marks']:<3d}  "
                  f"topic={topics_str}")
        if len(candidates) > 5:
            print(f"        ... and {len(candidates) - 5} more")
    return candidates


# ════════════════════════════════════════════════════════════════════
# STAGE 7 HELPERS — random shuffle + greedy selection
# ════════════════════════════════════════════════════════════════════

def fisher_yates_shuffle(lst):
    """
    In-place Fisher-Yates shuffle. O(n).

    Algorithm: for each position i from last down to 1,
    pick a random index j in [0, i] and swap lst[i] with lst[j].
    This guarantees a uniformly random permutation without using
    random.shuffle from the standard library.

    Used in STAGE 7 to randomise the candidate pool so every run
    produces a different worksheet for the same query parameters.
    """
    for i in range(len(lst)):
        j = random.randint(0,i)
        lst[i], lst[j] = lst[j], lst[i]
        
    return lst
    
def select_questions(
    candidates: List[Dict[str, Any]],
    target: int,
) -> tuple:
    """
    STAGE 7 — Randomly select questions to hit the target mark total.

    Two steps:
        1. fisher_yates_shuffle — randomise the candidate pool (O(n))
        2. Greedy fill — iterate the shuffled pool, pick a question if
           its marks fit under the remaining budget, stop when target hit.

    Returns (selected_questions, total_marks_achieved).
    """
    section("STAGE 7  ·  Hit the target marks")
    info(f"target = {target} marks   pool = {len(candidates)} questions")
    info("(random pick: shuffle the candidate questions randomly and use greedy algorith to pick questions until we reach the target marks)")

    #randomly shuffling candidate questions:
    candidates = fisher_yates_shuffle(candidates)

    t0 = time.perf_counter()
    selected = []
    total_marks = 0
    
    for q in candidates:
        if total_marks + q["marks"] <= target:
            selected.append(q)
            total_marks += q["marks"]
        if total_marks >= target:
            break
    dt = (time.perf_counter() - t0) * 1000

    kv("selection time",   f"{dt:.2f} ms")
    kv("questions chosen", len(selected))
    kv("marks achieved",   f"{total_marks}/{target}")
    if selected:
        print()
        info("selection:")
        for q in selected:
            print(f"        Q{q['id']:<35s}  "
                  f"y={q['year']}  marks={q['marks']:<3d}")
    return selected, total_marks


def generate_ws(selected: List[Dict[str, Any]], subject: str,
                   tier: str, actual: int) -> None:
    """
    STAGE 8 — Ask user to confirm, then compile and save the PDF worksheet.

    Calls:
        generate_worksheet() from worksheet_generator.py
        which uses PyMuPDF show_pdf_page() to copy question regions
        from the source Cambridge PDFs into a new A4 worksheet PDF.
    """
    if not selected:
        info("(nothing to compile — skipping worksheet generation)")
        return

    section("STAGE 8  ·  Compile the worksheet")
    print()
    try:
        choice = input("  generate the PDF worksheet now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if choice and choice.startswith("n"):
        info("skipped — selection retained in memory only")
        return

    title = f"{subject}_{tier}_{actual}marks"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, title + ".pdf")
    path = generate_worksheet(selected, output_path, title)
    info(f"open the worksheet: {os.path.abspath(path)}")

# ════════════════════════════════════════════════════════════════════
# MODE 2 — DATA STRUCTURE OPERATIONS DEMO
# These functions demonstrate each InvertedIndex class method in
# isolation using the real loaded index.
# ONLY called when user picks "Run data structure demo".
#
# NOTE ON THE TWO "SEARCH" FUNCTIONS:
#   run_search()   — MODE 1 full pipeline (stages 6a–6e), used for
#                    worksheet generation. Calls query+union+fetch.
#   _demo_search() — MODE 2 isolated demo of ONE index.query() call
#                    to show the O(1) lookup to the instructor.
#   They are completely separate and serve different purposes.
# ════════════════════════════════════════════════════════════════════

def show_data_structure_demo(index: InvertedIndex) -> None:
    """Main menu for MODE 2 — loops until user picks [0] Exit."""
    while True:
        print()
        print(SECTION)
        print("  BONUS  ·  InvertedIndex — Class Operations Demo")
        print(SECTION)
        print("    [1]  INSERT       index.insert(key, record)")
        print("    [2]  SEARCH       index.query(key)            ← O(1)")
        print("    [3]  UNION        index.union([keys])")
        print("    [4]  INTERSECT    index.intersect([keys])")
        print("    [5]  DELETE       index.remove_question(qid)")
        print("    [6]  VIEW TREE    index.view_tree()")
        print("    [7]  BENCHMARK    index.query() vs naive O(n) scan")
        print("    [0]  Exit")
        print()

        try:
            choice = input("  select an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if   choice == "1": _demo_insert(index)
        elif choice == "2": _demo_search(index)
        elif choice == "3": _demo_union(index)
        elif choice == "4": _demo_intersect(index)
        elif choice == "5": _demo_delete(index)
        elif choice == "6": _demo_view_tree(index)
        elif choice == "7": _demo_benchmark(index)
        elif choice == "0": break
        else: print("    invalid — pick 0–7")

def _demo_insert(index: InvertedIndex) -> None:
    """
    Demonstrate index.insert(key, record) using a real PDF.
    Parses the PDF, tags topics, builds composite keys,
    then inserts all extracted questions into the index.
    """
    from pdf_parser import parse_paper
    from topic_mapper import build_composite_keys, load_keyword_map, tag_question

    section("INSERT — index.insert(key, record)")
    info("parses a real Cambridge PDF, tags topics, inserts questions into the index")
    info("time per insert: O(1) amortised")
    print()

    flag = False
    while not flag:
        try:
            pdf_path = input(r"  enter path to PDF file (path: data\test directory\9702_s18_qp_21.pdf): ").strip()
        except (EOFError, KeyboardInterrupt):
            return

        if not os.path.exists(pdf_path):
            info("file not found — check the path and try again")
        else: flag = True

    print()
    info(f"calling: parse_paper('{pdf_path}')")
    questions = parse_paper(pdf_path)

    if not questions:
        info("no questions extracted from that PDF")
        return

    keyword_map = load_keyword_map(KEYWORD_MAP_PATH)

    before_store = len(index.question_store)
    before_keys  = len(index.main_index)

    info(f"tagging topics and calling index.insert() for each question...")
    print()

    for q in questions:
        topics = tag_question(q["text"], q["subject"], keyword_map, q["paper_type"])
        q["topic"] = topics
        keys = build_composite_keys(q["subject"], topics, q["paper_type"][:2])
        for key in keys:
            info(f"index.insert('{key}', record)  id={q['id']}")
            index.insert(key, q)

    print()
    kv("questions parsed",    len(questions))
    kv("question_store size", f"{before_store} → {len(index.question_store)}")
    kv("main_index keys",     f"{before_keys} → {len(index.main_index)}")
    info("all questions inserted successfully")


def _demo_search(index: InvertedIndex) -> None:
    """
    Demonstrate index.query(key) — isolated O(1) hash lookup.

    NOTE: this is NOT the same as run_search() which is the full
    worksheet pipeline. This demo shows a single raw dict lookup.
    """
    section("SEARCH — index.query(key)")
    info("single O(1) dict lookup — no scanning, no iteration")
    info("key format: {subject}_{topic}_{paper_type}")
    info("example:    9702_Kinematics_p2")
    print()

    try:
        search_key = input("  enter key to search: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    info(f"calling: index.query('{search_key}')")
    t0      = time.perf_counter()
    results = index.query(search_key)
    dt      = (time.perf_counter() - t0) * 1000

    print()
    kv("lookup time",   f"{dt:.3f} ms  ← O(1)")
    kv("results found", len(results))

    if not results:
        info("no questions found for that key — try another key")
        return

    print()
    info(f"found {len(results)} questions:")
    for qid in results:
        record  = index.question_store.get(qid, {})
        snippet = record.get("text", "")[:100].replace("\n", " ")
        print(f"    {'─' * 40}")
        print(f"    ID:    {qid}")
        print(f"    Marks: {record.get('marks', '?')}")
        print(f"    Text:  {snippet}...")
    print(f"    {'─' * 40}")

def _demo_union(index: InvertedIndex) -> None:
    """
    Demonstrate index.union([key1, key2]).
    Returns ids appearing in ANY of the listed keys.
    """
    section("UNION — index.union([key1, key2])")
    info("returns ids appearing in ANY of the listed keys")
    info("use case: 'Kinematics OR Dynamics questions'")
    info("time: O(k + total postings)")
    print()

    try:
        k1 = input("  key 1 [eg 9702_Kinematics_p2, 9702_Waves_p2, 9702_D.C. circuits_p2]: ").strip() or "9702_Kinematics_p2"
        k2 = input("  key 2 [9702_Dynamics_p2, 9702_Forces density and pressure_p2, 9702_Work energy and power_p2]:   ").strip() or "9702_Dynamics_p2"
    except (EOFError, KeyboardInterrupt):
        return

    p1 = index.query(k1)
    p2 = index.query(k2)
    kv(f"postings in key 1", len(p1))
    kv(f"postings in key 2", len(p2))

    info(f"calling: index.union(['{k1}', '{k2}'])")
    t0     = time.perf_counter()
    result = index.union([k1, k2])
    dt     = (time.perf_counter() - t0) * 1000

    print()
    kv("union time",         f"{dt:.3f} ms")
    kv("result size",        len(result))
    kv("duplicates removed", (len(p1) + len(p2)) - len(result))
    print()
    info("first 5 ids from union result:")
    for qid in result[:5]:
        print(f"        {qid}")    
        
def _demo_intersect(index: InvertedIndex) -> None:
    """
    Demonstrate index.intersect([key1, key2]).
    Returns ids appearing in ALL of the listed keys.
    """
    section("INTERSECT — index.intersect([key1, key2])")
    info("returns ids appearing in ALL of the listed keys")
    info("use case: 'questions tagged BOTH Kinematics AND Dynamics'")
    info("time: O(k × smallest postings list)")
    print()

    try:
        k1 = input("  key 1 [eg 9702_Kinematics_p2, 9702_Waves_p2, 9702_D.C. circuits_p2]: ").strip() or "9702_Kinematics_p2"
        k2 = input("  key 2 [9702_Dynamics_p2, 9702_Forces density and pressure_p2, 9702_Work energy and power_p2]:   ").strip() or "9702_Dynamics_p2"
    except (EOFError, KeyboardInterrupt):
        return

    p1 = index.query(k1)
    p2 = index.query(k2)
    kv(f"postings in key 1", len(p1))
    kv(f"postings in key 2", len(p2))

    info(f"calling: index.intersect(['{k1}', '{k2}'])")
    t0     = time.perf_counter()
    result = index.intersect([k1, k2])
    dt     = (time.perf_counter() - t0) * 1000

    print()
    kv("intersect time", f"{dt:.3f} ms")
    kv("result size",    len(result))
    print()
    if result:
        info("ids appearing under BOTH keys:")
        for qid in result[:5]:
            print(f"        {qid}")
    else:
        info("no questions appear under both keys simultaneously")

def _demo_delete(index: InvertedIndex) -> None:
    """
    Demonstrate index.remove_question(qid).
    Shows which keys the question appears in before deletion,
    then purges it and confirms it is gone from all postings lists.
    """
    section("DELETE — index.remove_question(qid)")
    info("purges the id from EVERY postings list in main_index")
    info("then removes the full record from question_store")
    print()

    try:
        target_id = input("  enter question ID to delete: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if target_id not in index.question_store:
        info(f"question ID '{target_id}' not found in question_store")
        return

    # Show which keys it appears in before deletion
    keys_before = [k for k, ids in index.main_index.items() if target_id in ids]
    info(f"'{target_id}' appears in {len(keys_before)} keys before deletion:")
    for k in keys_before[:5]:
        print(f"        {k}")

    print()
    info(f"calling: index.remove_question('{target_id}')")
    t0 = time.perf_counter()
    index.remove_question(target_id)
    dt = (time.perf_counter() - t0) * 1000

    keys_after = [k for k, ids in index.main_index.items() if target_id in ids]
    print()
    kv("deletion time",   f"{dt:.3f} ms")
    kv("keys before",     len(keys_before))
    kv("keys after",      len(keys_after))
    kv("still in store?", target_id in index.question_store)
    info(f"question '{target_id}' purged from all postings lists and question_store")
    
          
def _demo_view_tree(index: InvertedIndex) -> None:
    """
    Demonstrate index.view_tree().
    This is a method defined on the InvertedIndex class itself —
    it walks main_index and prints the tree structure.
    """
    
    section("VIEW TREE — index.view_tree()")
    info("method of InvertedIndex — walks main_index and prints the tree structure")
    info("shows composite keys with their postings lists beneath them")
    print()

    # Perform view operation using class method
    info("calling: index.view_tree()")
    print()
    index.view_tree(len(index.main_index))
    print()
    kv("total keys",      len(index.main_index))
    kv("total questions", len(index.question_store))



def _demo_benchmark(index: InvertedIndex) -> None:
    """
    Benchmark index.query() vs a naive O(n) linear scan.
    Runs 1000 iterations of each and compares total time.
    This is the core argument for why an inverted index exists.
    """
    section("OPERATION: BENCHMARK — inverted index vs naive linear scan")
    info("runs 1000 lookups each, compares total time")

    if not index.question_store:
        info("no data to benchmark")
        return

    # Pick the first available key
    target_key = next(iter(index.main_index))
    all_records = list(index.question_store.values())
    loops = 1000

    info(f"query key: {target_key}")
    info(f"index size: {len(all_records)} questions")
    info(f"runs: {loops}")
    print()

    # Inverted index
    t0 = time.perf_counter()
    for _ in range(loops):
        _ = index.query(target_key)
    index_total = (time.perf_counter() - t0)

    # Naive scan — scan every record and check subject + text
    parts = target_key.split("_")
    subject = parts[0]
    topic = parts[1] if len(parts) > 1 else ""

    t0 = time.perf_counter()
    for _ in range(loops):
        matches = []
        for r in all_records:
            if r.get("subject") == subject and topic.lower() in r.get("text", "").lower():
                matches.append(r)
    naive_total = (time.perf_counter() - t0)

    kv("inverted index time", f"{index_total:.4f} s")
    kv("naive scan time",     f"{naive_total:.4f} s")

    if index_total > 0:
        ratio = naive_total / index_total
        kv("speedup",         f"{ratio:.1f}x faster")
    info("this demonstrates why an inverted index exists — O(1) vs O(n)")

# ════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def main() -> None:
    banner("CS201  ·  Inverted Index Past-Paper Worksheet Generator  ·  Demo")

    try:
        index = load_or_build_index()

        # Load the keyword map once so topic filtering can use it
        keyword_map: Dict[str, Any] = {}
        if KEYWORD_MAP_PATH and os.path.isfile(KEYWORD_MAP_PATH):
            with open(KEYWORD_MAP_PATH, "r", encoding="utf-8") as f:
                keyword_map = json.load(f)
        while True:   
            section("Chose what you want to do: ")
            chosen = ask_choice(
            "Choice: ",
                ["Generate a Worksheet", "Run data structure demo", "End demo"],
                )
            if chosen == "Generate a Worksheet":
                while True:
                    subject = None
                    while not subject:
                        # ── Curiculum level selection: A-level or O-level ──────────────────────────
                        level = pick_level()
                    
                        # ── subject selection ──────────────────────────
                        subject = pick_subject(index, level)
                    
                    # ── tier selection for A-Level ──────────────────────────
                    tier = pick_tier(level)

                        
                    # ── Paper style: MCQ or Theory ────────────────────────────────
                    paper_style = pick_paper_style()

                    # ── Topics are now tier-aware ─────────────────────────────────
                    topics = None
                    while not topics:
                        topics = pick_topics(index, subject, tier, keyword_map)
                        if not topics:
                            info("no topics selected — restarting")
                        

                    # pick_paper_type() is gone — tier already encodes that choice
                    yfrom, yto = pick_year_range(index, subject)

                    section("REVIEW  ·  what you've selected")
                    kv("level",        level)
                    kv("tier",         tier)
                    kv("paper style",  paper_style)
                    kv("subject",      f"{SUBJECTS.get(subject)}  ({subject})")
                    kv("topics",       ", ".join(topics))
                    kv("year range",   f"{yfrom}–{yto}")
                    target = ask_int("target marks", 30, 5, 200)
                    kv("target marks", target)

                    candidates = run_search(
                        index, subject, topics, tier, paper_style, yfrom, yto,
                    )

                    if not candidates:
                        info("no questions found — relax your filters")
                    else:
                        selected, actual = select_questions(candidates, target)
                        generate_ws(selected, subject, tier, actual)

                    print()
                    try:
                        again = input("  another query? [y/N]  ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        again = "n"
                    if not again.startswith("y"):
                        break
            elif chosen == "Run data structure demo":
                show_data_structure_demo(index)

            else:
                print()
                break
        
            
        
    except KeyboardInterrupt:
        print("\n  interrupted — bye")
        sys.exit(0)

    banner("--------------End of demo--------------")


if __name__ == "__main__":
    main()