"""
test_worksheet_generator.py — Unit tests for the worksheet PDF generator.

These tests verify that generate_worksheet() produces valid PDF files
with the correct number of pages and proper structure.
"""

import os
import sys
import unittest

# Add project root to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worksheet_generator import generate_worksheet

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_PDF = os.path.join(PROJECT_ROOT, "data", "papers", "qp", "9702_w25_qp_22.pdf")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "tests", "temp")


# ── Helper: build a fake question record pointing at a real PDF ──
def make_question(qid, page, y0, y1, marks=5):
    return {
        "id": qid,
        "subject": "9702",
        "paper_type": "p22",
        "session": "w25",
        "year": 2025,
        "topic": ["Kinematics"],
        "marks": marks,
        "text": "Sample question",
        "pdf": TEST_PDF,
        "regions": [
            {"page": page, "rect": [0, y0, 595.3, y1]},
        ],
    }


class TestWorksheetGeneration(unittest.TestCase):
    """Test that generate_worksheet() produces a valid PDF."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TEST_PDF):
            raise unittest.SkipTest("Test PDF not found: " + TEST_PDF)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    def tearDown(self):
        # Clean up any generated PDFs after each test
        output_path = os.path.join(OUTPUT_DIR, "test_output.pdf")
        if os.path.exists(output_path):
            os.remove(output_path)

    @classmethod
    def tearDownClass(cls):
        # Remove temp dir if empty
        if os.path.exists(OUTPUT_DIR):
            try:
                os.rmdir(OUTPUT_DIR)
            except OSError:
                pass

    def test_generates_pdf_file(self):
        questions = [make_question("q1", page=3, y0=53.8, y1=717.6)]
        output_path = os.path.join(OUTPUT_DIR, "test_output.pdf")

        result = generate_worksheet(questions, output_path, "Test Worksheet")

        self.assertTrue(os.path.exists(result))
        self.assertTrue(result.endswith(".pdf"))

    def test_output_file_not_empty(self):
        questions = [make_question("q1", page=3, y0=53.8, y1=717.6)]
        output_path = os.path.join(OUTPUT_DIR, "test_output.pdf")

        generate_worksheet(questions, output_path, "Test Worksheet")

        file_size = os.path.getsize(output_path)
        self.assertGreater(file_size, 0)

    def test_multiple_questions(self):
        questions = [
            make_question("q1", page=3, y0=53.8, y1=717.6),
            make_question("q2", page=5, y0=53.8, y1=717.6),
        ]
        output_path = os.path.join(OUTPUT_DIR, "test_output.pdf")

        generate_worksheet(questions, output_path, "Multi-Question Test")

        self.assertTrue(os.path.exists(output_path))

    def test_page_count_reasonable(self):
        """A single near-full-page question should produce 1-2 pages."""
        import fitz

        questions = [make_question("q1", page=3, y0=53.8, y1=717.6)]
        output_path = os.path.join(OUTPUT_DIR, "test_output.pdf")

        generate_worksheet(questions, output_path, "Page Count Test")

        doc = fitz.open(output_path)
        page_count = len(doc)
        doc.close()
        # 1 page for header + 1 question region = should be 1-2 pages
        self.assertGreaterEqual(page_count, 1)
        self.assertLessEqual(page_count, 3)

    def test_total_marks_in_header(self):
        """The header should show the correct total marks."""
        import fitz

        questions = [
            make_question("q1", page=3, y0=53.8, y1=400.0, marks=8),
            make_question("q2", page=5, y0=53.8, y1=400.0, marks=12),
        ]
        output_path = os.path.join(OUTPUT_DIR, "test_output.pdf")

        generate_worksheet(questions, output_path, "Marks Test")

        doc = fitz.open(output_path)
        first_page_text = doc[0].get_text()
        doc.close()
        # Total marks should be 8 + 12 = 20
        self.assertIn("20", first_page_text)

    def test_empty_question_list(self):
        """An empty question list should still produce a valid PDF."""
        output_path = os.path.join(OUTPUT_DIR, "test_output.pdf")

        result = generate_worksheet([], output_path, "Empty Test")

        self.assertTrue(os.path.exists(result))


if __name__ == "__main__":
    unittest.main()
