import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from overline.scoring import ppr_points


class ScoringTest(unittest.TestCase):
    def test_passing_and_receiving_ppr(self):
        points = ppr_points(
            {
                "passing_yards": 300,
                "passing_tds": 2,
                "interceptions": 1,
                "receptions": 5,
                "receiving_yards": 50,
                "receiving_tds": 1,
            }
        )
        self.assertAlmostEqual(points, 34.0)

    def test_fumble_lost_costs_two(self):
        self.assertAlmostEqual(ppr_points({"rushing_fumbles_lost": 1}), -2.0)

    def test_missing_stats_are_zero(self):
        self.assertEqual(ppr_points({}), 0.0)


if __name__ == "__main__":
    unittest.main()
