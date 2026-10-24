import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from overline.projections import form_line


class ProjectionTest(unittest.TestCase):
    def test_empty_history_is_the_position_mean(self):
        self.assertEqual(form_line([], 12.5), 12.5)

    def test_one_game_shrinks_toward_the_position(self):
        # Weight on the single game is 1 / 5. Line = 0.2 * 10 + 0.8 * 20.
        self.assertAlmostEqual(form_line([10.0], 20.0), 18.0)

    def test_a_long_stable_history_stays_near_that_level(self):
        line = form_line([15.0] * 40, 8.0)
        self.assertGreater(line, 14.0)
        self.assertLess(line, 15.1)


if __name__ == "__main__":
    unittest.main()
