"""
worksheet_generator.py — A4 PDF worksheet builder.

Takes a list of selected question records and compiles them into a
clean A4 PDF using PyMuPDF's vector-preserving show_pdf_page() method.

Pipeline:
    1. Open a blank A4 document and stamp a header (title + total marks).
    2. For each question, open its source Cambridge PDF and copy each
       region using show_pdf_page() — this preserves vectors, fonts,
       and diagrams at full quality without rasterisation.
    3. Each region is cropped to remove Cambridge's margin sidebars,
       barcodes, and footer chrome before stamping.
    4. A thin dashed separator line is drawn between questions.
    5. The completed worksheet is saved and compressed to disk.

Key constants (all in PDF points, 1 point = 1/72 inch):
    PAGE_W / PAGE_H   — A4 dimensions (595 × 842)
    WS_MARGIN_*       — worksheet page margins
    SRC_CROP_*        — crop bounds applied to source Cambridge PDFs
    USABLE_W          — available content width after margins
"""

import os
import fitz
from typing import Any, Dict, List, Tuple

# ── A4 dimensions in PDF points (1 point = 1/72 inch) ───────────────
PAGE_W = 595.0
PAGE_H = 842.0

# ── Worksheet margins ────────────────────────────────────────────────
WS_MARGIN_LEFT   = 45.0
WS_MARGIN_RIGHT  = 45.0
WS_MARGIN_TOP    = 45.0
WS_MARGIN_BOTTOM = 50.0

# ── Source-PDF crop zone ─────────────────────────────────────────────
# Cambridge past-paper layout has:
#   - Left margin sidebar ("DO NOT WRITE…")  up to about x=50
#   - Right margin sidebar ("DO NOT WRITE…") from about x=555
#   - Header zone (barcode, page number)     up to about y=55
#   - Footer zone (© UCLES, QR code)         from about y=790
# We crop to the CONTENT rectangle only:
SRC_CROP_LEFT   = 42.0
SRC_CROP_RIGHT  = 548.0
SRC_CROP_TOP    = 60
SRC_CROP_BOTTOM = 785.0

# Usable content width on the worksheet page after left and right margins
USABLE_W = PAGE_W - WS_MARGIN_LEFT - WS_MARGIN_RIGHT  # 595 - 45 - 45 = 505

def generate_worksheet(
    selected_questions: List[Dict[str, Any]],
    output_path: str,
    title: str = "Worksheet"
) -> str:
    """
    Build an A4 PDF worksheet from a list of selected question records.

    Creates a new blank A4 document, stamps a header, then iterates
    through the question list calling _stamp_question() for each one.
    The final PDF is saved with garbage collection and deflate compression.

    Args:
        selected_questions: list of question dicts. Each must contain:
                                pdf     — absolute path to the source PDF
                                marks   — integer mark value
                                regions — list of {page, rect} dicts
        output_path:        where to save the worksheet PDF
        title:              text shown in the worksheet header

    Returns:
        output_path (the path the file was saved to)
    """

    ws_doc = fitz.open()  # new empty document
    ws_page = ws_doc.new_page(width=PAGE_W, height=PAGE_H)

    total_marks = sum(q.get("marks", 0) for q in selected_questions)
    y_cursor = _stamp_header(ws_page, title, total_marks)

    for q_num, question in enumerate(selected_questions, start=1):
        ws_page, y_cursor = _stamp_question(
            ws_doc, ws_page, y_cursor, question, q_num
        )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    ws_doc.save(output_path, garbage=3, deflate=True)
    ws_doc.close()
    return output_path


# ── Header ───────────────────────────────────────────────────────────

def _stamp_header(page: fitz.Page, title: str, total_marks: int) -> float:
    """
    Stamp the worksheet title and total marks onto the first page,
    then draw a horizontal rule beneath them.

    Args:
        page:        the fitz.Page to draw on
        title:       worksheet title string
        total_marks: sum of marks across all selected questions

    Returns:
        y cursor position just below the header rule, ready for
        the first question to be stamped.
    """

    y = WS_MARGIN_TOP + 18
    page.insert_text(
        (WS_MARGIN_LEFT, y),
        title,
        fontsize=15,
        fontname="helv",
        color=(0, 0, 0),
    )

    y += 16
    page.insert_text(
        (WS_MARGIN_LEFT, y),
        f"Total Marks: {total_marks}",
        fontsize=9,
        fontname="helv",
        color=(0.35, 0.35, 0.35),
    )

    y += 10
    page.draw_line(
        fitz.Point(WS_MARGIN_LEFT, y),
        fitz.Point(PAGE_W - WS_MARGIN_RIGHT, y),
        color=(0, 0, 0),
        width=0.8,
    )

    return y + 15  # a little breathing room below the line


# ── Per-question stamping ────────────────────────────────────────────

def _stamp_question(
    ws_doc: fitz.Document,
    ws_page: fitz.Page,
    y_cursor: float,
    question: Dict[str, Any],
    q_number: int,
) -> Tuple[fitz.Page, float]:
    """
    Stamp all regions of one question onto the worksheet.

    For each region in question['regions']:
        1. Build a clip rect by intersecting the parser's region rect
           with SRC_CROP_* bounds to remove Cambridge chrome.
        2. Scale the region to fit the usable worksheet width.
        3. Apply a fit check — if the region is too tall for the
           remaining space on the current page, either shrink it
           (within 15% tolerance) or open a new page.
        4. Call ws_page.show_pdf_page() to stamp the vector content.

    After all regions, draws a thin dashed separator line.

    Args:
        ws_doc:    the worksheet fitz.Document (needed to add new pages)
        ws_page:   the current fitz.Page being written to
        y_cursor:  current vertical position on the page (in points)
        question:  full question record dict
        q_number:  1-based question number (currently unused in output
                   but kept for future labelling)

    Returns:
        (ws_page, y_cursor) — updated page and cursor after stamping.
        ws_page may be a new page object if a page break occurred.
    """

    src_doc = fitz.open(question["pdf"])

    for region in question["regions"]:
        src_page_num = region["page"]
        raw_rect = fitz.Rect(region["rect"])  # full-width rect from parser

        # ── Intersect with the clean content zone ────────────────────
        # The parser gives us the vertical extent of the question.
        # We tighten the horizontal and vertical bounds to exclude the
        # margin sidebars, header barcodes, and footer lines.
        clip = fitz.Rect(
            max(raw_rect.x0, SRC_CROP_LEFT),
            max(raw_rect.y0, SRC_CROP_TOP),
            min(raw_rect.x1, SRC_CROP_RIGHT),
            min(raw_rect.y1, SRC_CROP_BOTTOM),
        )

        if clip.is_empty or clip.width < 10 or clip.height < 10:
            continue  # degenerate region — skip

        # ── Scale to fit the usable width ────────────────────────────
        # scale maps source content width → worksheet usable width.
        # Since source PDFs are A4 (595 wide) and we crop margins,
        # scale is typically very close to 1.0.
        src_content_w = clip.width        # e.g. 548 - 42 = 506
        scale = USABLE_W / src_content_w  # e.g. 505 / 506 ≈ 1.0
        dest_h = clip.height * scale

        # ── Fit check ────────────────────────────────────────────────
        space_left = PAGE_H - WS_MARGIN_BOTTOM - y_cursor

        if dest_h <= space_left:
            # Fits as-is — no action needed
            pass
        elif dest_h <= space_left * 1.15:
            # Region is only slightly too tall (within 15%).
            # Shrink it to fit rather than wasting the rest of the page.
            # This avoids the "empty first page" problem when a near-
            # full-page region follows the header.
            shrink = space_left / dest_h
            scale *= shrink
            dest_h = space_left
        else:
            # Too tall to shrink gracefully — start a fresh page.
            ws_page = ws_doc.new_page(width=PAGE_W, height=PAGE_H)
            y_cursor = WS_MARGIN_TOP
            space_left = PAGE_H - WS_MARGIN_BOTTOM - y_cursor
            # If it still doesn't fit a blank page, shrink to page
            if dest_h > space_left:
                shrink = space_left / dest_h
                scale *= shrink
                dest_h = space_left

        dest_w = clip.width * scale
        dest_rect = fitz.Rect(
            WS_MARGIN_LEFT,
            y_cursor,
            WS_MARGIN_LEFT + dest_w,
            y_cursor + dest_h,
        )

        ws_page.show_pdf_page(
            dest_rect,
            src_doc,
            src_page_num,
            clip=clip,
        )

        y_cursor += dest_h

    src_doc.close()

    # ── Thin separator line after each question ──────────────────────
    y_cursor += 6
    if y_cursor < PAGE_H - WS_MARGIN_BOTTOM:
        ws_page.draw_line(
            fitz.Point(WS_MARGIN_LEFT, y_cursor),
            fitz.Point(PAGE_W - WS_MARGIN_RIGHT, y_cursor),
            color=(0.75, 0.75, 0.75),
            width=0.4,
            dashes="[3 3]",
        )
    y_cursor += 12

    return ws_page, y_cursor

