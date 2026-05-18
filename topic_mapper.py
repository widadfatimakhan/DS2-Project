"""
topic_mapper.py — Keyword-to-topic tagging engine.

Uses a keyword frequency scoring approach (bag-of-words) to assign topic
labels to extracted questions. Keyword maps are derived from Cambridge
syllabuses and stored as JSON files.

AS/A2 AWARENESS
───────────────
The keyword_map.json now uses a two-level structure per A-Level subject:

    {
        "9702": {
            "AS": { "Kinematics": [...], "Dynamics": [...], ... },
            "A2": { "Oscillations": [...], "Capacitance": [...], ... }
        },
        "5054": {
            "ALL": { "Forces": [...], "Waves": [...], ... }
        }
    }

O-Level subjects use a single "ALL" tier since every paper covers the
full syllabus without an AS/A2 split.

The paper_type passed to tag_question() is used to determine which tier
of keywords to search, so p11/p21/p31 (AS) papers are never tagged with
A2 topics and vice versa.
"""

import json
import re
from typing import Any, Dict, List, Optional

# Import tier data from config (avoids circular imports if used standalone)
try:
    from config import A_LEVEL_SUBJECTS, O_LEVEL_SUBJECTS, PAPER_TIER_MAP
except ImportError:
    # Fallback definitions so this module works standalone
    A_LEVEL_SUBJECTS = {"9702", "9701", "9709"}
    O_LEVEL_SUBJECTS = {"4024", "5070", "5054"}
    PAPER_TIER_MAP = {"1": "AS", "2": "AS", "3": "AS", "4": "A2", "5": "A2"}


# ── Tier resolution ──────────────────────────────────────────────

def get_paper_tier(subject_code: str, paper_type: str) -> str:
    """
    Determine the curriculum tier of a paper.

    For A-Level subjects (9702, 9701, 9709) the first digit of the paper
    number encodes the tier:
        1/2/3  →  "AS"
        4/5    →  "A2"

    For O-Level subjects (5054, 4024, 5070) the entire syllabus is
    undivided, so we return "ALL".

    Args:
        subject_code: e.g. "9702"
        paper_type:   e.g. "p21"  (always lowercase, leading "p")

    Returns:
        "AS" | "A2" | "ALL"

    Examples:
        get_paper_tier("9702", "p11")  → "AS"
        get_paper_tier("9702", "p41")  → "A2"
        get_paper_tier("5054", "p21")  → "ALL"
    """
    if subject_code in O_LEVEL_SUBJECTS:
        return "ALL"

    # paper_type is like "p21" — strip the leading "p" and take first digit
    paper_num = paper_type.lstrip("p")
    if paper_num and paper_num[0].isdigit():
        return PAPER_TIER_MAP.get(paper_num[0], "ALL")

    return "ALL"


def _resolve_topic_dict(
    subject_map: Any,
    tier: str,
) -> Dict[str, List[str]]:
    """
    Given a subject's entry from keyword_map and a resolved tier,
    return the flat {topic: [keywords]} dict to search against.

    Handles both new (tiered) and legacy (flat) keyword_map formats:

    New format:
        { "AS": { "Kinematics": [...] }, "A2": { "Oscillations": [...] } }

    Legacy format (backward compatible):
        { "Kinematics": [...], "Dynamics": [...] }
    """
    # New tiered format — has "AS" or "A2" as top-level keys
    if isinstance(subject_map, dict) and ("AS" in subject_map or "A2" in subject_map or "ALL" in subject_map):
        if tier == "ALL":
            # Merge all tiers for O-Level
            merged: Dict[str, List[str]] = {}
            for tier_dict in subject_map.values():
                if isinstance(tier_dict, dict):
                    merged.update(tier_dict)
            return merged
        else:
            return subject_map.get(tier, {})

    # Legacy flat format — treat everything as one pool
    return subject_map if isinstance(subject_map, dict) else {}


# ── Keyword map I/O ──────────────────────────────────────────────

def load_keyword_map(path: str) -> Dict[str, Any]:
    """
    Load the keyword-to-topic mapping JSON file.

    Supports both new tiered format and legacy flat format:

    New (tiered) format:
    {
        "9702": {
            "AS": {
                "Kinematics": ["velocity", "acceleration", "displacement"],
                "Dynamics":   ["force", "newton", "momentum"]
            },
            "A2": {
                "Oscillations": ["shm", "simple harmonic", "damping"],
                "Capacitance":  ["capacitor", "capacitance", "dielectric"]
            }
        },
        "5054": {
            "ALL": {
                "Forces": ["force", "weight", "friction"],
                "Waves":  ["wave", "frequency", "amplitude"]
            }
        }
    }

    Legacy (flat) format (still supported for backward compatibility):
    {
        "9702": {
            "Kinematics": ["velocity", "acceleration"],
            ...
        }
    }

    Args:
        path: str, path to keyword_map.json.

    Returns:
        dict mapping subject_code → (tiered or flat) topic dict.
    """
    with open(path, "r") as f:
        return json.load(f)


# ── Core tagging ─────────────────────────────────────────────────

def tag_question(
    question_text: str,
    subject_code: str,
    keyword_map: Dict[str, Any],
    paper_type: str = "",
) -> List[str]:
    """
    Assign topic label(s) to a question using bag-of-words keyword scoring.

    Only keywords from the appropriate curriculum tier are searched:
    - AS papers  (p1x, p2x, p3x) → AS keywords only
    - A2 papers  (p4x, p5x)      → A2 keywords only
    - O-Level    (any paper)      → ALL keywords

    This prevents MCQ questions on AS papers from being tagged with
    A2 topics that haven't been taught yet, and vice versa.

    Steps:
    1. Resolve the paper tier (AS / A2 / ALL).
    2. Select only the topic dict for that tier.
    3. Normalize the question text (lowercase, strip punctuation).
    4. Score each topic by counting keyword hits.
    5. Return the top-scoring topic(s); fall back to "Uncategorized".

    Args:
        question_text: str, raw text extracted from the question.
        subject_code:  str, e.g. "9702".
        keyword_map:   dict, loaded from load_keyword_map().
        paper_type:    str, e.g. "p21". Used to determine the tier.
                       Pass "" to search all topics (legacy behaviour).

    Returns:
        list of str, topic label(s). Usually 1; occasionally 2 for
        cross-topic questions (second topic scores ≥ 60% of first).
    """
    if subject_code not in keyword_map:
        return ["Uncategorized"]

    # 1. Resolve tier and get the topic dict to search
    if paper_type != "":
        tier = get_paper_tier(subject_code, paper_type)
    else:
        tier = "ALL"
    topics_to_search = _resolve_topic_dict(keyword_map[subject_code], tier)

    if not topics_to_search:
        return ["Uncategorized"]

    # 2. Normalize question text
    normalized = question_text.lower()
    normalized = re.sub(r"[*_#\[\]()!]", " ", normalized)   # strip markdown
    normalized = re.sub(r"[^a-z0-9\s\-]", " ", normalized)  # keep alphanum + hyphen
    words = normalized.split()

    # 3. Score each topic
    scores: Dict[str, int] = {}
    for topic, keywords in topics_to_search.items():
        count = 0
        for keyword in keywords:
            kw = keyword.lower()
            if " " in kw:
                # Multi-word phrase: substring search on full normalized text
                count += normalized.count(kw)
            else:
                # Single word: exact word-list match (avoids partial hits)
                count += words.count(kw)
        if count > 0:
            scores[topic] = count

    if not scores:
        return ["Uncategorized"]

    # 4. Rank and select
    def get_score(item):
        return item[1]
        
    ranked = sorted(scores.items(), key=get_score, reverse=True)
    best_score = ranked[0][1]
    result = []
    result.append(ranked[0][0])

    # Include subsequent topics only if they score ≥ 60% of the top topic
    for topic_name, score in ranked[1:]:
        

        if score >= best_score * 0.6:
            result.append(topic_name)

    return result


# ── Key construction ─────────────────────────────────────────────

def build_composite_keys(
    subject_code: str,
    topics: List[str],
    paper_type: str,
) -> List[str]:
    """
    Construct composite inverted-index keys.

    Key format: {SubjectCode}_{Topic}_{PaperType}
    Example:    "9702_Kinematics_p21"

    The tier (AS/A2) is implicitly encoded in the paper_type
    (p2x = AS, p4x = A2), so it is not repeated in the key.
    This keeps keys human-readable and backward-compatible.

    Args:
        subject_code: str, e.g. "9702".
        topics:       list of str, topic labels from tag_question().
        paper_type:   str, e.g. "p21".

    Returns:
        list of composite key strings, one per topic.
    """
    keys = []
    for topic in topics:
        new_key = subject_code + "_" + topic + "_" + paper_type
        keys.append(new_key)
    return keys




# print(get_paper_tier("5054", "p1"))