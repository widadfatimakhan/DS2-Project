"""
pdf_parser.py — Bounding Box (BBox) PDF ingestion and question extraction.

Works by reading the PDF line-by-line, grouping text into 5-point vertical buckets 
to fix misalignments, and using an x < 85 "left margin fence" to find question numbers.
"""

import os
import re
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF


# ── Layout constants (A4 Cambridge past paper geometry) ─────────────
MARGIN_TOP: float = 60.0  # Skip PDF header region (page numbers, logos)
MARGIN_BOTTOM: float = 788.0  # Skip PDF footer region (copyright, page refs)
Q_NUM_MAX_X: float = 85.0  # Question numbers are always in the left margin


def parse_paper(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Parse a Cambridge past paper PDF and extract questions as structured records.

    Each record contains:
        id          — unique question identifier e.g. '9702_w25_p21_q1'
        subject     — subject code e.g. '9702'
        paper_type  — paper variant e.g. 'p21'
        session     — session code e.g. 'w25'
        year        — integer year e.g. 2025
        topic       — placeholder 'Unknown' (filled in by tag_question() later)
        marks       — total marks extracted from [N] brackets
        pdf         — absolute path to the source PDF
        text        — raw extracted text of the question
        regions     — list of {page, rect} dicts, one per page the question
                      spans, with rect = [x0, y0, x1, y1] in PDF points.
                      Used by worksheet_generator.py to crop question areas
                      from the source PDF without rasterisation.

    Expects PapaCambridge naming convention:
        {subject}_{session}_qp_{variant}.pdf
        e.g. 9702_w25_qp_13.pdf

    Args:
        pdf_path: path to the Cambridge question-paper PDF

    Returns:
        list of question record dicts, one per question found in the paper.
        Returns [] if the filename does not match the expected convention.
    """

    # ── 1. Extract metadata from filename ─────────────────────────────
    file_name = os.path.basename(pdf_path)
    name_no_ext = os.path.splitext(file_name)[0]
    parts = name_no_ext.split("_")

    if len(parts) >= 4:
        subject_code = parts[0]  # e.g. "9702"
        session_year = parts[1]  # e.g. "w25"
        variant = parts[3]  # e.g. "13"
        paper_type = f"p{variant}"  # e.g. "p13"
        try:
            actual_year = 2000 + int(session_year[1:])
        except ValueError:
            actual_year = 2025
    else:
        print(f"Warning: Filename '{file_name}' does not match PapaCambridge standard.")
        return []

    # ── 2. Regex: Match isolated question numbers (e.g. "3 ") but ignore mid-text numbers. ──────


    q_num_pattern = re.compile(r"^(\d{1,2})(?:\s+\S|\s*$)")

    # ── 3. Parse PDF line-by-line ──────────────────────────────────────
    doc = fitz.open(pdf_path)

    questions: List[Dict[str, Any]] = []
    current_q: Optional[Dict[str, Any]] = None
    expected_q: int = 1

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_dict = page.get_text("dict")
        page_width = page.rect.width

        # Collect all text lines from all blocks on this page
        all_lines: List[tuple] = []
        for block in page_dict["blocks"]:
            if block.get("type") != 0:  # skip image blocks
                continue
            for line in block["lines"]:
                lx0, ly0, lx1, ly1 = line["bbox"]
                # Join spans into a single string for this line
                line_text = " ".join(span["text"] for span in line["spans"]).strip()
                if line_text:
                    all_lines.append((lx0, ly0, lx1, ly1, line_text))

        # ── 5-Point Bucket Sort ────────────────────────────────────────────
        # Fixes 1-2px vertical misalignments. Snaps y0 to the nearest 5, forcing
        # text on the same visual row to tie, so x0 tie-breaker sorts left-to-right!
        def visual_row_sort_key(line_tuple: tuple) -> tuple:
            """Group lines into 5-pt vertical buckets, then sort by x-position."""
            x_pos = line_tuple[0]
            y_pos = line_tuple[1]
            bucketed_y = round(y_pos / 5) * 5
            return (bucketed_y, x_pos)

        all_lines.sort(key=visual_row_sort_key)

        for lx0, ly0, lx1, ly1, line_text in all_lines:
            # ── Skip header / footer zones ─────────────────────────────
            if ly0 < MARGIN_TOP or ly0 > MARGIN_BOTTOM:
                continue

            # ── Detect start of next question ──────────────────────────
            # Only check inside the Left Margin Fence (x0 < 85) to ignore formula fractions.
            if lx0 < Q_NUM_MAX_X:
                match = q_num_pattern.match(line_text)
                if match and int(match.group(1)) == expected_q:
                    # Save the completed previous question
                    if current_q:
                        questions.append(current_q)

                    # Initialise the new question record
                    current_q = {
                        "id": f"{subject_code}_{session_year}_{paper_type}_q{expected_q}",
                        "subject": subject_code,
                        "paper_type": paper_type,
                        "session": session_year,
                        "year": actual_year,
                        "topic": "Unknown",
                        "marks": 0,
                        "pdf": os.path.abspath(pdf_path),
                        "text": "",
                        "regions": [],
                    }
                    expected_q += 1

            # ── Accumulate content into the active question ────────────
            if current_q is None:
                continue

            current_q["text"] += line_text + "\n"

            # Extract marks e.g. [2] or [ 3 ]
            for m in re.findall(r"\[\s*(\d+)\s*\]", line_text):
                current_q["marks"] += int(m)

            # ── Update master crop box (scissors template) ─────────────────
            if not current_q["regions"] or current_q["regions"][-1]["page"] != page_num:
                # Start a new full-width green crop box with 10px padding above
                current_q["regions"].append(
                    {
                        "page": page_num,
                        "rect": [0, max(0.0, ly0 - 10), page_width, ly1 + 10],
                    }
                )
            else:
                # Pull the bottom edge of the crop box further down as we read more text
                current_q["regions"][-1]["rect"][3] = max(
                    current_q["regions"][-1]["rect"][3], ly1 + 10
                )

    # Append the final question
    if current_q:
        questions.append(current_q)

    # ── MCQ mark fix ───────────────────────────────────────────────────
    # Paper 1 questions carry no [N] marks bracket — each is worth 1 mark.
    for q in questions:
        if q["marks"] == 0 and paper_type.startswith("p1"):
            q["marks"] = 1

    doc.close()
    return questions


# ── Batch helper ────────────────────────────────────────────────────


def parse_all_papers(papers_dir: str, subject_code: str) -> List[Dict[str, Any]]:
    """
    Walk `papers_dir` recursively and parse every PDF found.

    Note: subject_code parameter is accepted but not used internally —
    parse_paper() extracts the subject code from the filename directly.
    This function is a convenience batch wrapper around parse_paper().

    Args:
        papers_dir:   root directory to walk e.g. 'data/papers/qp'
        subject_code: accepted for API compatibility but not used

    Returns:
        flat list of all question records extracted from all PDFs found
    """
    all_questions: List[Dict[str, Any]] = []
    for root, _, files in os.walk(papers_dir):
        for file in files:
            if file.endswith(".pdf"):
                questions = parse_paper(os.path.join(root, file))
                all_questions.extend(questions)
    return all_questions

