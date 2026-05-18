"""
build_index.py — Ingestion pipeline: PDF → InvertedIndex.

Walks a directory of Cambridge past-paper PDFs, parses each one,
tags questions with topics, builds composite keys, and inserts
everything into an InvertedIndex instance which is then saved to disk.

The index is saved to:
    data/index/physics_master_index.json

Run directly to rebuild the index from scratch:
    python build_index.py
"""

import os
from typing import Any

from inverted_index import InvertedIndex
from pdf_parser import parse_paper
from topic_mapper import build_composite_keys, load_keyword_map, tag_question


# ════════════════════════════════════════════════════════════════════
# INDEX BUILD PIPELINE
# ════════════════════════════════════════════════════════════════════

def build_master_index(data_dir: str, keyword_map_path: str) -> InvertedIndex:
    """
    Ingest all Cambridge past-paper PDFs in `data_dir` and build a
    master InvertedIndex.

    Pipeline:
        1. Initialise an empty InvertedIndex and load the keyword map.
        2. Walk `data_dir` and filter for question-paper PDFs
           (filename must end in .pdf and contain '_qp_').
        3. Parse each PDF with parse_paper() to extract question records.
        4. Tag each question with topics using tag_question() — this
           uses a bag-of-words keyword match against the keyword_map,
           restricted to the correct AS/A2 tier based on paper_type.
        5. Build composite index keys (subject_topic_papertype) and
           insert each question into the index via index.insert().
        6. Persist the completed index to disk as JSON.

    Args:
        data_dir:         path to the folder containing question-paper PDFs
                          e.g. 'data/papers/qp'
        keyword_map_path: path to the keyword map JSON file
                          e.g. 'data/keywords/keyword_map.json'

    Returns:
        The populated InvertedIndex instance.
    """

    # ── 1. Initialise ────────────────────────────────────────────────
    index       = InvertedIndex()
    keyword_map = load_keyword_map(keyword_map_path)

    # ── 2. Walk the PDF directory ────────────────────────────────────
    for file_name in os.listdir(data_dir):

        # Only process Cambridge question-paper PDFs
        # Naming convention: {subject}_{session}_qp_{variant}.pdf
        # e.g. 9702_w25_qp_21.pdf
        if not (file_name.endswith(".pdf") and "_qp_" in file_name):
            continue

        pdf_path = os.path.join(data_dir, file_name)
        print(f"  ingesting {file_name}...")

        # ── 3. Parse the PDF ─────────────────────────────────────────
        # parse_paper() extracts questions with their text, marks,
        # bounding-box regions, and metadata (subject, session, year).
        questions = parse_paper(pdf_path)

        for q in questions:

            # ── 4. Tag with topics ───────────────────────────────────
            # tag_question() scores each topic by keyword frequency.
            # Passing paper_type restricts the search to the correct
            # tier (AS keywords for p1x/p2x, A2 keywords for p4x/p5x).
            topics   = tag_question(q["text"], q["subject"], keyword_map, q["paper_type"])
            q["topic"] = topics

            # ── 5. Build keys and insert ─────────────────────────────
            # Key format: "{subject}_{topic}_{paper_type_prefix}"
            # e.g. "9702_Kinematics_p2"
            # paper_type[:2] gives the prefix: "p21" → "p2"
            keys = build_composite_keys(q["subject"], topics, q["paper_type"][:2])
            for key in keys:
                index.insert(key, q)

    # ── 6. Persist to disk ───────────────────────────────────────────
    index_path = "data/index/physics_master_index.json"
    index.save(index_path)
    print(f"\n  master index saved → {index_path}")
    print(f"  keys: {len(index.main_index)}   questions: {len(index.question_store)}")

    return index


# ════════════════════════════════════════════════════════════════════
# ENTRY POINT — rebuild the index from scratch
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    build_master_index("data/papers/qp", "data/keywords/keyword_map.json")