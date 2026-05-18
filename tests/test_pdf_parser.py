"""
test_pdf_parser.py — Unit tests for the PDF parser.

These tests use a real PDF from the data directory as a fixture.
They verify that parse_paper() correctly extracts question boundaries,
metadata, marks, and bounding-box regions from Cambridge past papers.
"""

import os
import sys
import unittest

# Add project root to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_parser import parse_paper

# Path to a known test PDF (Paper 22 has lots of diagrams)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_PDF_P22 = os.path.join(PROJECT_ROOT, "data", "papers", "qp", "9702_w25_qp_22.pdf")
TEST_PDF_P11 = os.path.join(PROJECT_ROOT, "data", "papers", "qp", "9702_w25_qp_11.pdf")


class TestParserMetadata(unittest.TestCase):
    """Check that parse_paper() extracts correct metadata from filename."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TEST_PDF_P22):
            raise unittest.SkipTest("Test PDF not found: " + TEST_PDF_P22)
        cls.questions = parse_paper(TEST_PDF_P22)

    def test_returns_list(self):
        self.assertIsInstance(self.questions, list)

    def test_at_least_one_question_found(self):
        self.assertGreater(len(self.questions), 0)

    def test_subject_code(self):
        for q in self.questions:
            self.assertEqual(q["subject"], "9702")

    def test_session(self):
        for q in self.questions:
            self.assertEqual(q["session"], "w25")

    def test_paper_type(self):
        for q in self.questions:
            self.assertEqual(q["paper_type"], "p22")

    def test_year(self):
        for q in self.questions:
            self.assertEqual(q["year"], 2025)


class TestParserQuestionStructure(unittest.TestCase):
    """Check that each extracted question has the required fields."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TEST_PDF_P22):
            raise unittest.SkipTest("Test PDF not found: " + TEST_PDF_P22)
        cls.questions = parse_paper(TEST_PDF_P22)

    def test_required_fields_present(self):
        required_fields = ["id", "subject", "paper_type", "session", "year",
                           "marks", "text", "pdf", "regions"]
        for q in self.questions:
            for field in required_fields:
                self.assertIn(field, q, "Missing field: " + field + " in " + q["id"])

    def test_id_format(self):
        # IDs should look like: 9702_w25_p22_q1, 9702_w25_p22_q2, etc.
        for q in self.questions:
            self.assertTrue(q["id"].startswith("9702_w25_p22_q"),
                            "Bad ID format: " + q["id"])

    def test_marks_are_positive(self):
        for q in self.questions:
            self.assertGreater(q["marks"], 0,
                               "Marks should be > 0 for " + q["id"])

    def test_text_not_empty(self):
        for q in self.questions:
            self.assertTrue(len(q["text"].strip()) > 0,
                            "Text should not be empty for " + q["id"])

    def test_regions_not_empty(self):
        for q in self.questions:
            self.assertGreater(len(q["regions"]), 0,
                               "Regions should not be empty for " + q["id"])

    def test_region_has_page_and_rect(self):
        for q in self.questions:
            for region in q["regions"]:
                self.assertIn("page", region)
                self.assertIn("rect", region)
                self.assertEqual(len(region["rect"]), 4,
                                 "Rect should have 4 values [x0, y0, x1, y1]")


class TestParserQuestionCount(unittest.TestCase):
    """Verify the parser finds the expected number of questions."""

    def test_p22_question_count(self):
        if not os.path.exists(TEST_PDF_P22):
            self.skipTest("Test PDF not found: " + TEST_PDF_P22)
        questions = parse_paper(TEST_PDF_P22)
        # Paper 22 structured papers typically have 5-7 questions
        self.assertGreaterEqual(len(questions), 4,
                                "Expected at least 4 questions in Paper 22")

    def test_p11_question_count(self):
        if not os.path.exists(TEST_PDF_P11):
            self.skipTest("Test PDF not found: " + TEST_PDF_P11)
        questions = parse_paper(TEST_PDF_P11)
        # Paper 11 MCQ papers typically have 30+ questions
        self.assertGreaterEqual(len(questions), 20,
                                "Expected at least 20 questions in Paper 11 (MCQ)")


class TestParserSequentialIds(unittest.TestCase):
    """Verify questions come out in sequential order."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TEST_PDF_P22):
            raise unittest.SkipTest("Test PDF not found: " + TEST_PDF_P22)
        cls.questions = parse_paper(TEST_PDF_P22)

    def test_ids_are_sequential(self):
        for i in range(len(self.questions)):
            expected_suffix = "q" + str(i + 1)
            actual_id = self.questions[i]["id"]
            self.assertTrue(actual_id.endswith(expected_suffix),
                            "Expected " + expected_suffix + " but got " + actual_id)


if __name__ == "__main__":
    unittest.main()
