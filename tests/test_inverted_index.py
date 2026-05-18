"""
test_inverted_index.py — Unit tests for InvertedIndex data structure.
"""

import json
import os
import sys
import tempfile
import unittest

# Add project root to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inverted_index import InvertedIndex


# ── Helper: build a sample question record ──────────────────────
def make_record(qid, subject="9702", paper_type="p21", year=2025, marks=5):
    return {
        "id": qid,
        "subject": subject,
        "paper_type": paper_type,
        "year": year,
        "marks": marks,
        "text": "Sample question text for " + qid,
        "pdf": "data/papers/qp/sample.pdf",
        "regions": [],
    }


class TestInsert(unittest.TestCase):
    """Tests for the insert() method."""

    def setUp(self):
        self.index = InvertedIndex()

    def test_insert_single_record(self):
        record = make_record("q1")
        self.index.insert("9702_Kinematics_p21", record)

        # The key should now exist in the main_index
        self.assertIn("9702_Kinematics_p21", self.index.main_index)
        # The question id should be in the postings list
        self.assertEqual(self.index.main_index["9702_Kinematics_p21"], ["q1"])
        # The record should be in the question_store
        self.assertIn("q1", self.index.question_store)

    def test_insert_multiple_records_same_key(self):
        r1 = make_record("q1")
        r2 = make_record("q2")
        self.index.insert("9702_Kinematics_p21", r1)
        self.index.insert("9702_Kinematics_p21", r2)

        postings = self.index.main_index["9702_Kinematics_p21"]
        self.assertEqual(len(postings), 2)
        self.assertIn("q1", postings)
        self.assertIn("q2", postings)

    def test_insert_duplicate_skipped(self):
        record = make_record("q1")
        self.index.insert("9702_Kinematics_p21", record)
        self.index.insert("9702_Kinematics_p21", record)

        # Should still only have one entry, not two
        postings = self.index.main_index["9702_Kinematics_p21"]
        self.assertEqual(len(postings), 1)

    def test_insert_same_record_different_keys(self):
        record = make_record("q1")
        self.index.insert("9702_Kinematics_p21", record)
        self.index.insert("9702_Dynamics_p21", record)

        # Both keys should exist
        self.assertIn("q1", self.index.main_index["9702_Kinematics_p21"])
        self.assertIn("q1", self.index.main_index["9702_Dynamics_p21"])
        # But only one copy in the store
        self.assertEqual(len(self.index.question_store), 1)


class TestQuery(unittest.TestCase):
    """Tests for the query() method."""

    def setUp(self):
        self.index = InvertedIndex()
        self.index.insert("9702_Kinematics_p21", make_record("q1"))
        self.index.insert("9702_Kinematics_p21", make_record("q2"))

    def test_query_existing_key(self):
        result = self.index.query("9702_Kinematics_p21")
        self.assertEqual(len(result), 2)
        self.assertIn("q1", result)
        self.assertIn("q2", result)

    def test_query_missing_key(self):
        result = self.index.query("9702_Waves_p21")
        self.assertEqual(result, [])


class TestUnion(unittest.TestCase):
    """Tests for the union() method (OR search)."""

    def setUp(self):
        self.index = InvertedIndex()
        self.index.insert("9702_Kinematics_p21", make_record("q1"))
        self.index.insert("9702_Dynamics_p21", make_record("q2"))
        self.index.insert("9702_Dynamics_p21", make_record("q3"))

    def test_union_two_keys(self):
        result = self.index.union(["9702_Kinematics_p21", "9702_Dynamics_p21"])
        self.assertEqual(len(result), 3)

    def test_union_with_overlap(self):
        # Insert q1 under both keys
        self.index.insert("9702_Dynamics_p21", make_record("q1"))
        result = self.index.union(["9702_Kinematics_p21", "9702_Dynamics_p21"])
        # q1 should appear only once (deduplicated)
        self.assertEqual(result.count("q1"), 1)

    def test_union_with_missing_key(self):
        result = self.index.union(["9702_Kinematics_p21", "9702_Nonexistent_p21"])
        # Should still return results from the valid key
        self.assertIn("q1", result)

    def test_union_empty_keys(self):
        result = self.index.union([])
        self.assertEqual(result, [])


class TestIntersect(unittest.TestCase):
    """Tests for the intersect() method (AND search)."""

    def setUp(self):
        self.index = InvertedIndex()
        # q1 is tagged under both Kinematics and Dynamics
        record_q1 = make_record("q1")
        self.index.insert("9702_Kinematics_p21", record_q1)
        self.index.insert("9702_Dynamics_p21", record_q1)
        # q2 is only under Dynamics
        self.index.insert("9702_Dynamics_p21", make_record("q2"))

    def test_intersect_finds_common(self):
        result = self.index.intersect(["9702_Kinematics_p21", "9702_Dynamics_p21"])
        self.assertEqual(len(result), 1)
        self.assertIn("q1", result)

    def test_intersect_no_overlap(self):
        self.index.insert("9702_Waves_p21", make_record("q3"))
        result = self.index.intersect(["9702_Kinematics_p21", "9702_Waves_p21"])
        self.assertEqual(result, [])

    def test_intersect_missing_key(self):
        result = self.index.intersect(["9702_Kinematics_p21", "9702_Nonexistent_p21"])
        self.assertEqual(result, [])

    def test_intersect_empty_keys(self):
        result = self.index.intersect([])
        self.assertEqual(result, [])


class TestFetchAndFilter(unittest.TestCase):
    """Tests for fetch_documents() and filter_by_year()."""

    def setUp(self):
        self.index = InvertedIndex()
        self.index.insert("key1", make_record("q1", year=2023))
        self.index.insert("key1", make_record("q2", year=2024))
        self.index.insert("key1", make_record("q3", year=2025))

    def test_fetch_all_no_filter(self):
        results = self.index.fetch_documents(["q1", "q2", "q3"])
        self.assertEqual(len(results), 3)

    def test_fetch_with_year_filter(self):
        results = self.index.fetch_documents(["q1", "q2", "q3"], year_from=2024, year_to=2025)
        self.assertEqual(len(results), 2)
        ids = [r["id"] for r in results]
        self.assertNotIn("q1", ids)

    def test_fetch_nonexistent_id(self):
        results = self.index.fetch_documents(["q999"])
        self.assertEqual(results, [])

    def test_filter_by_year(self):
        all_records = self.index.fetch_documents(["q1", "q2", "q3"])
        filtered = self.index.filter_by_year(all_records, 2025, 2025)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "q3")


class TestRemoveQuestion(unittest.TestCase):
    """Tests for the remove_question() method."""

    def setUp(self):
        self.index = InvertedIndex()
        self.index.insert("9702_Kinematics_p21", make_record("q1"))
        self.index.insert("9702_Kinematics_p21", make_record("q2"))

    def test_remove_existing(self):
        self.index.remove_question("q1")
        # Should be gone from the store
        self.assertNotIn("q1", self.index.question_store)
        # Should be gone from the postings list
        self.assertNotIn("q1", self.index.main_index["9702_Kinematics_p21"])
        # q2 should still be there
        self.assertIn("q2", self.index.main_index["9702_Kinematics_p21"])

    def test_remove_nonexistent(self):
        # Should not crash
        self.index.remove_question("q999")
        self.assertEqual(len(self.index.question_store), 2)


class TestSaveLoad(unittest.TestCase):
    """Tests for save() and load() persistence."""

    def setUp(self):
        self.index = InvertedIndex()
        self.index.insert("9702_Kinematics_p21", make_record("q1"))
        self.index.insert("9702_Dynamics_p21", make_record("q2"))

    def test_save_and_load_roundtrip(self):
        # Save to a temp file
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, "test_index.json")

        try:
            self.index.save(temp_path)

            # Load into a fresh index
            new_index = InvertedIndex()
            new_index.load(temp_path)

            # Verify data survived the roundtrip
            self.assertEqual(new_index.query("9702_Kinematics_p21"), ["q1"])
            self.assertEqual(new_index.query("9702_Dynamics_p21"), ["q2"])
            self.assertIn("q1", new_index.question_store)
            self.assertIn("q2", new_index.question_store)
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)


if __name__ == "__main__":
    unittest.main()
