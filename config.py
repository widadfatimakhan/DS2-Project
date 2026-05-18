"""
config.py — Project-wide constants and path definitions.
"""

import os
from typing import Dict, List, Set

# ── Directory Paths ──────────────────────────────────────────────
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
DATA_DIR: str = os.path.join(BASE_DIR, "data")
PAPERS_DIR: str = os.path.join(DATA_DIR, "papers")
KEYWORDS_DIR: str = os.path.join(DATA_DIR, "keywords")
OUTPUT_DIR: str = os.path.join(DATA_DIR, "output")
TEMPLATES_DIR: str = os.path.join(BASE_DIR, "templates")
STATIC_DIR: str = os.path.join(BASE_DIR, "static")

# ── Index Persistence ───────────────────────────────────────────
INDEX_PATH: str = os.path.join(DATA_DIR, "index", "physics_master_index.json")
QUESTION_DB_PATH: str = os.path.join(DATA_DIR, "question_db.json")

# ── Keyword Map ─────────────────────────────────────────────────
KEYWORD_MAP_PATH: str = os.path.join(KEYWORDS_DIR, "keyword_map.json")

# ── PDF Generation Settings ─────────────────────────────────────
PAGE_WIDTH: int = 595  # A4 width in points
PAGE_HEIGHT: int = 842  # A4 height in points
MARGIN_TOP: int = 60
MARGIN_BOTTOM: int = 60
MARGIN_LEFT: int = 40
MARGIN_RIGHT: int = 40

# ── Supported Subjects ──────────────────────────────────────────
# Maps subject code → display name
SUBJECTS: Dict[str, str] = {
    "9702": "A-Level Physics",
    "9701": "A-Level Chemistry",
    "9709": "A-Level Mathematics",
    "4024": "O-Level Mathematics",
    "5070": "O-Level Chemistry",
    "5054": "O-Level Physics",
}

# ── Subject Level Classification ─────────────────────────────────
# A-Level subjects have a meaningful AS / A2 split.
# O-Level subjects use a flat topic list (no split).
A_LEVEL_SUBJECTS: Set[str] = {"9702", "9701", "9709"}
O_LEVEL_SUBJECTS: Set[str] = {"4024", "5070", "5054"}

# ── Paper Tier Map ───────────────────────────────────────────────
# Cambridge encodes the exam level in the FIRST digit of the paper number.
#
# Paper numbering convention (A-Level):
#   1x  →  AS  Multiple Choice (MCQ)          e.g. p11, p12, p13
#   2x  →  AS  Structured Questions            e.g. p21, p22, p23
#   3x  →  AS  Practical / Advanced Practical  e.g. p31, p32, p33
#   4x  →  A2  Structured Questions            e.g. p41, p42, p43
#   5x  →  A2  Practical / Advanced Practical  e.g. p51, p52, p53
#
# For O-Level subjects every paper covers the full syllabus,
# so get_paper_tier() returns "ALL" for those (see topic_mapper.py).
#
# Key:   first digit of the paper number string (e.g. "2" from "p21")
# Value: "AS" | "A2"
PAPER_TIER_MAP: Dict[str, str] = {
    "1": "AS",
    "2": "AS",
    "3": "AS",
    "4": "A2",
    "5": "A2",
}

# ── Paper Types ──────────────────────────────────────────────────
PAPER_TYPES: List[str] = ["P1", "P2", "P3", "P4", "P5"]


