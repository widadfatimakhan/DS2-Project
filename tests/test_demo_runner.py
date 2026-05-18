"""
test_demo_runner.py — Unit tests for the demo runner's filtering logic.

Tests that the paper style filter (MCQ vs Theory) correctly separates
question types, and that the search pipeline returns only questions
from the expected paper variants.
"""

import os
import sys
import unittest

# Add project root to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import INDEX_PATH, KEYWORD_MAP_PATH
from inverted_index import InvertedIndex
from demo_runner import _resolve_paper_variants, _topics_for_tier

import json


def load_test_index():
    """Load the real index for integration-style tests."""
    if not os.path.exists(INDEX_PATH):
        return None
    index = InvertedIndex(keyword_map_path=KEYWORD_MAP_PATH)
    index.load(INDEX_PATH)
    return index


def load_keyword_map():
    """Load the keyword map for topic filtering tests."""
    if not os.path.exists(KEYWORD_MAP_PATH):
        return {}
    with open(KEYWORD_MAP_PATH, "r") as f:
        return json.load(f)


class TestResolvePaperVariants(unittest.TestCase):
    """Tests for _resolve_paper_variants() with MCQ/Theory filtering."""

    @classmethod
    def setUpClass(cls):
        cls.index = load_test_index()
        if cls.index is None:
            raise unittest.SkipTest("Index file not found: " + INDEX_PATH)

    def test_as_mcq_returns_only_p1x(self):
        """MCQ style + AS tier should only return p1x variants."""
        variants = _resolve_paper_variants(self.index, "9702", "AS", "MCQ")
        for v in variants:
            self.assertTrue(v.startswith("p1"),
                            "MCQ should only have p1x variants, got: " + v)

    def test_as_theory_returns_only_p2x(self):
        """Theory style + AS tier should only return p2x variants."""
        variants = _resolve_paper_variants(self.index, "9702", "AS", "Theory")
        for v in variants:
            self.assertTrue(v.startswith("p2"),
                            "AS Theory should only have p2x variants, got: " + v)

    def test_a2_theory_returns_only_p4x(self):
        """Theory style + A2 tier should only return p4x variants."""
        variants = _resolve_paper_variants(self.index, "9702", "A2", "Theory")
        for v in variants:
            self.assertTrue(v.startswith("p4"),
                            "A2 Theory should only have p4x variants, got: " + v)

    def test_mcq_and_theory_no_overlap(self):
        """MCQ and Theory variants should never overlap."""
        mcq = set(_resolve_paper_variants(self.index, "9702", "AS", "MCQ"))
        theory = set(_resolve_paper_variants(self.index, "9702", "AS", "Theory"))
        overlap = mcq & theory
        self.assertEqual(overlap, set(),
                         "MCQ and Theory should not share variants: " + str(overlap))

    def test_as_mcq_not_empty(self):
        """There should be at least one MCQ variant for AS Physics."""
        variants = _resolve_paper_variants(self.index, "9702", "AS", "MCQ")
        self.assertGreater(len(variants), 0,
                           "Expected at least one MCQ variant for AS 9702")

    def test_as_theory_not_empty(self):
        """There should be at least one Theory variant for AS Physics."""
        variants = _resolve_paper_variants(self.index, "9702", "AS", "Theory")
        self.assertGreater(len(variants), 0,
                           "Expected at least one Theory variant for AS 9702")


class TestMCQQuestionsAreAllOneMark(unittest.TestCase):
    """Verify that MCQ-filtered questions are actually 1-mark MCQs."""

    @classmethod
    def setUpClass(cls):
        cls.index = load_test_index()
        if cls.index is None:
            raise unittest.SkipTest("Index file not found: " + INDEX_PATH)

    def test_mcq_questions_are_one_mark(self):
        """All questions from MCQ paper variants should be 1 mark."""
        mcq_variants = _resolve_paper_variants(self.index, "9702", "AS", "MCQ")
        # Get all question IDs from MCQ keys
        all_ids = []
        topics = self.index.list_topics("9702")
        for topic in topics:
            for variant in mcq_variants:
                key = "9702_" + topic + "_" + variant
                all_ids.extend(self.index.query(key))

        # Remove duplicates
        seen = set()
        unique_ids = []
        for qid in all_ids:
            if qid not in seen:
                seen.add(qid)
                unique_ids.append(qid)

        # Fetch and check marks
        records = self.index.fetch_documents(unique_ids)
        for r in records:
            self.assertEqual(r["marks"], 1,
                             r["id"] + " is from MCQ but has " + str(r["marks"]) + " marks")


class TestTheoryQuestionsHaveMultipleMarks(unittest.TestCase):
    """Verify that Theory-filtered questions have more than 1 mark."""

    @classmethod
    def setUpClass(cls):
        cls.index = load_test_index()
        if cls.index is None:
            raise unittest.SkipTest("Index file not found: " + INDEX_PATH)

    def test_theory_questions_have_multiple_marks(self):
        """Theory questions should generally have more than 1 mark."""
        theory_variants = _resolve_paper_variants(self.index, "9702", "AS", "Theory")
        all_ids = []
        topics = self.index.list_topics("9702")
        for topic in topics:
            for variant in theory_variants:
                key = "9702_" + topic + "_" + variant
                all_ids.extend(self.index.query(key))

        # Remove duplicates
        seen = set()
        unique_ids = []
        for qid in all_ids:
            if qid not in seen:
                seen.add(qid)
                unique_ids.append(qid)

        records = self.index.fetch_documents(unique_ids)
        # At least some should have > 1 mark
        multi_mark = [r for r in records if r["marks"] > 1]
        self.assertGreater(len(multi_mark), 0,
                           "Expected at least some theory questions with > 1 mark")


class TestTheoryQuestionsHaveRegions(unittest.TestCase):
    """Theory questions should have bounding box regions for PDF clipping."""

    @classmethod
    def setUpClass(cls):
        cls.index = load_test_index()
        if cls.index is None:
            raise unittest.SkipTest("Index file not found: " + INDEX_PATH)

    def test_all_theory_questions_have_regions(self):
        """Every theory question should have at least one region."""
        theory_variants = _resolve_paper_variants(self.index, "9702", "AS", "Theory")
        all_ids = []
        topics = self.index.list_topics("9702")
        for topic in topics:
            for variant in theory_variants:
                key = "9702_" + topic + "_" + variant
                all_ids.extend(self.index.query(key))

        seen = set()
        unique_ids = []
        for qid in all_ids:
            if qid not in seen:
                seen.add(qid)
                unique_ids.append(qid)

        records = self.index.fetch_documents(unique_ids)
        for r in records:
            self.assertGreater(len(r.get("regions", [])), 0,
                               r["id"] + " has no regions for PDF clipping")


class TestTopicsForTier(unittest.TestCase):
    """Tests for _topics_for_tier() tier-aware topic filtering."""

    @classmethod
    def setUpClass(cls):
        cls.index = load_test_index()
        cls.keyword_map = load_keyword_map()
        if cls.index is None:
            raise unittest.SkipTest("Index file not found: " + INDEX_PATH)

    def test_as_topics_exist(self):
        """AS tier should return at least some topics."""
        topics = _topics_for_tier(self.index, "9702", "AS", self.keyword_map)
        self.assertGreater(len(topics), 0)

    def test_a2_topics_exist(self):
        """A2 tier should return at least some topics."""
        topics = _topics_for_tier(self.index, "9702", "A2", self.keyword_map)
        self.assertGreater(len(topics), 0)

    def test_as_and_a2_topics_are_different(self):
        """AS and A2 should have mostly different topics."""
        as_topics = set(_topics_for_tier(self.index, "9702", "AS", self.keyword_map))
        a2_topics = set(_topics_for_tier(self.index, "9702", "A2", self.keyword_map))
        # They should not be identical sets
        self.assertNotEqual(as_topics, a2_topics,
                            "AS and A2 topics should differ")

    def test_both_includes_all(self):
        """'Both' tier should include topics from AS and A2."""
        as_topics = set(_topics_for_tier(self.index, "9702", "AS", self.keyword_map))
        a2_topics = set(_topics_for_tier(self.index, "9702", "A2", self.keyword_map))
        both_topics = set(_topics_for_tier(self.index, "9702", "Both", self.keyword_map))

        # Both should be a superset of AS and A2
        self.assertTrue(as_topics.issubset(both_topics),
                        "Both should include all AS topics")
        self.assertTrue(a2_topics.issubset(both_topics),
                        "Both should include all A2 topics")


class TestNoMixedPaperTypes(unittest.TestCase):
    """The critical test: verify MCQ filter never returns structured Qs."""

    @classmethod
    def setUpClass(cls):
        cls.index = load_test_index()
        if cls.index is None:
            raise unittest.SkipTest("Index file not found: " + INDEX_PATH)

    def test_mcq_filter_returns_no_structured_questions(self):
        """Questions from MCQ filter should all have paper_type starting with p1."""
        mcq_variants = _resolve_paper_variants(self.index, "9702", "AS", "MCQ")
        topics = self.index.list_topics("9702")

        all_ids = []
        for topic in topics:
            for variant in mcq_variants:
                key = "9702_" + topic + "_" + variant
                all_ids.extend(self.index.query(key))

        seen = set()
        unique_ids = []
        for qid in all_ids:
            if qid not in seen:
                seen.add(qid)
                unique_ids.append(qid)

        records = self.index.fetch_documents(unique_ids)
        for r in records:
            self.assertTrue(r["paper_type"].startswith("p1"),
                            "MCQ filter leaked a structured Q: " + r["id"]
                            + " (paper_type=" + r["paper_type"] + ")")

    def test_theory_filter_returns_no_mcq_questions(self):
        """Questions from Theory filter should all have paper_type starting with p2 or p4."""
        theory_variants = _resolve_paper_variants(self.index, "9702", "AS", "Theory")
        topics = self.index.list_topics("9702")

        all_ids = []
        for topic in topics:
            for variant in theory_variants:
                key = "9702_" + topic + "_" + variant
                all_ids.extend(self.index.query(key))

        seen = set()
        unique_ids = []
        for qid in all_ids:
            if qid not in seen:
                seen.add(qid)
                unique_ids.append(qid)

        records = self.index.fetch_documents(unique_ids)
        for r in records:
            pt = r["paper_type"]
            self.assertTrue(pt.startswith("p2") or pt.startswith("p4"),
                            "Theory filter leaked an MCQ: " + r["id"]
                            + " (paper_type=" + pt + ")")


if __name__ == "__main__":
    unittest.main()
