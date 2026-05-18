"""
test_topic_mapper.py — Unit tests for the topic tagging engine.
"""

import os
import sys
import unittest

# Add project root to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from topic_mapper import (
    get_paper_tier,
    _resolve_topic_dict,
    tag_question,
    build_composite_keys,
)


# ── Small keyword map used across all tests ─────────────────────
SAMPLE_KEYWORD_MAP = {
    "9702": {
        "AS": {
            "Kinematics": ["velocity", "acceleration", "displacement", "free fall"],
            "Dynamics": ["force", "newton", "momentum", "impulse"],
            "Waves": ["wave", "frequency", "amplitude", "wavelength"],
        },
        "A2": {
            "Oscillations": ["shm", "simple harmonic", "damping", "resonance"],
            "Capacitance": ["capacitor", "capacitance", "dielectric", "time constant"],
        },
    },
    "5054": {
        "ALL": {
            "Forces": ["force", "weight", "friction", "tension"],
            "Waves": ["wave", "frequency", "amplitude"],
        },
    },
}


class TestGetPaperTier(unittest.TestCase):
    """Tests for get_paper_tier()."""

    def test_as_paper_p11(self):
        self.assertEqual(get_paper_tier("9702", "p11"), "AS")

    def test_as_paper_p21(self):
        self.assertEqual(get_paper_tier("9702", "p21"), "AS")

    def test_as_paper_p31(self):
        self.assertEqual(get_paper_tier("9702", "p31"), "AS")

    def test_a2_paper_p41(self):
        self.assertEqual(get_paper_tier("9702", "p41"), "A2")

    def test_a2_paper_p52(self):
        self.assertEqual(get_paper_tier("9702", "p52"), "A2")

    def test_o_level_returns_all(self):
        self.assertEqual(get_paper_tier("5054", "p21"), "ALL")
        self.assertEqual(get_paper_tier("4024", "p11"), "ALL")

    def test_empty_paper_type(self):
        result = get_paper_tier("9702", "")
        self.assertEqual(result, "ALL")


class TestResolveTopicDict(unittest.TestCase):
    """Tests for _resolve_topic_dict()."""

    def test_resolve_as_tier(self):
        result = _resolve_topic_dict(SAMPLE_KEYWORD_MAP["9702"], "AS")
        self.assertIn("Kinematics", result)
        self.assertIn("Dynamics", result)
        self.assertNotIn("Oscillations", result)

    def test_resolve_a2_tier(self):
        result = _resolve_topic_dict(SAMPLE_KEYWORD_MAP["9702"], "A2")
        self.assertIn("Oscillations", result)
        self.assertNotIn("Kinematics", result)

    def test_resolve_all_merges_tiers(self):
        result = _resolve_topic_dict(SAMPLE_KEYWORD_MAP["9702"], "ALL")
        # Should have topics from both AS and A2
        self.assertIn("Kinematics", result)
        self.assertIn("Oscillations", result)

    def test_resolve_o_level(self):
        result = _resolve_topic_dict(SAMPLE_KEYWORD_MAP["5054"], "ALL")
        self.assertIn("Forces", result)
        self.assertIn("Waves", result)

    def test_resolve_nonexistent_tier(self):
        result = _resolve_topic_dict(SAMPLE_KEYWORD_MAP["9702"], "X99")
        self.assertEqual(result, {})


class TestTagQuestion(unittest.TestCase):
    """Tests for the tag_question() scoring engine."""

    def test_single_topic_match(self):
        text = "Calculate the velocity and acceleration of the object."
        result = tag_question(text, "9702", SAMPLE_KEYWORD_MAP, "p21")
        self.assertIn("Kinematics", result)

    def test_dynamics_keywords(self):
        text = "A force is applied and the momentum changes. Calculate the impulse."
        result = tag_question(text, "9702", SAMPLE_KEYWORD_MAP, "p21")
        self.assertIn("Dynamics", result)

    def test_a2_topic_not_tagged_on_as_paper(self):
        text = "The capacitor has a capacitance of 100 microfarads."
        result = tag_question(text, "9702", SAMPLE_KEYWORD_MAP, "p21")
        # p21 is AS, so A2 topics like Capacitance should NOT appear
        self.assertNotIn("Capacitance", result)

    def test_a2_topic_tagged_on_a2_paper(self):
        text = "The capacitor has a capacitance of 100 microfarads."
        result = tag_question(text, "9702", SAMPLE_KEYWORD_MAP, "p41")
        # p41 is A2, so Capacitance SHOULD appear
        self.assertIn("Capacitance", result)

    def test_unknown_subject_returns_uncategorized(self):
        text = "Some random question text."
        result = tag_question(text, "9999", SAMPLE_KEYWORD_MAP, "p21")
        self.assertEqual(result, ["Uncategorized"])

    def test_no_keywords_match_returns_uncategorized(self):
        text = "The cat sat on the mat."
        result = tag_question(text, "9702", SAMPLE_KEYWORD_MAP, "p21")
        self.assertEqual(result, ["Uncategorized"])

    def test_multi_word_keyword(self):
        text = "The system undergoes simple harmonic motion with damping."
        result = tag_question(text, "9702", SAMPLE_KEYWORD_MAP, "p41")
        self.assertIn("Oscillations", result)

    def test_o_level_uses_all_topics(self):
        text = "A wave has a certain frequency and amplitude."
        result = tag_question(text, "5054", SAMPLE_KEYWORD_MAP, "p11")
        self.assertIn("Waves", result)

    def test_empty_text(self):
        result = tag_question("", "9702", SAMPLE_KEYWORD_MAP, "p21")
        self.assertEqual(result, ["Uncategorized"])


class TestBuildCompositeKeys(unittest.TestCase):
    """Tests for build_composite_keys()."""

    def test_single_topic(self):
        keys = build_composite_keys("9702", ["Kinematics"], "p21")
        self.assertEqual(keys, ["9702_Kinematics_p21"])

    def test_multiple_topics(self):
        keys = build_composite_keys("9702", ["Kinematics", "Dynamics"], "p21")
        self.assertEqual(len(keys), 2)
        self.assertIn("9702_Kinematics_p21", keys)
        self.assertIn("9702_Dynamics_p21", keys)

    def test_empty_topics(self):
        keys = build_composite_keys("9702", [], "p21")
        self.assertEqual(keys, [])


if __name__ == "__main__":
    unittest.main()
