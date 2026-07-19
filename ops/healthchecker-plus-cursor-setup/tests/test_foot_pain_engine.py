from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.intelligence.foot_pain_engine import FootPainEngine


class FootPainEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = FootPainEngine()

    def test_medication_edema(self) -> None:
        result = self.engine.evaluate(
            pain_location="ankle",
            swelling=True,
            symmetry="one_side",
            onset_speed="gradual",
            recent_med_change=True,
            glucose=110,
            kidney_status="normal",
            symptoms=[],
        )
        self.assertEqual(result["likely_cause"], "medication_edema")
        self.assertGreaterEqual(result["confidence"], 0.8)

    def test_gout(self) -> None:
        result = self.engine.evaluate(
            pain_location="big_toe",
            swelling=False,
            symmetry="one_side",
            onset_speed="sudden",
            recent_med_change=False,
            glucose=110,
            kidney_status="normal",
            symptoms=["sharp_pain", "joint_focus"],
        )
        self.assertEqual(result["likely_cause"], "gout")

    def test_undetermined_fallback(self) -> None:
        result = self.engine.evaluate(
            pain_location="heel",
            swelling=False,
            symmetry="both",
            onset_speed="gradual",
            recent_med_change=False,
            glucose=95,
            kidney_status="normal",
            symptoms=[],
        )
        self.assertEqual(result["likely_cause"], "undetermined")


if __name__ == "__main__":
    unittest.main()
