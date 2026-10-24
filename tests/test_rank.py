import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from overline.features import CONTEXT_FEATURES, FeatureRow
from overline.model import Prediction, Slot, fit_model
from overline.rank import RankedPlayer, rank_week


def blank_row(name, projection, actual, is_home):
    values = {feature: 0.0 for feature in CONTEXT_FEATURES}
    values["projection"] = projection
    values["is_home"] = float(is_home)
    values["games_played"] = 8.0
    return FeatureRow(
        player_id=name,
        name=name,
        position="WR",
        team="NOR",
        opponent="SOU",
        site="home" if is_home else "away",
        season=2024,
        week=8,
        actual=actual,
        values=values,
    )


class RankTest(unittest.TestCase):
    def test_score_can_outrank_a_larger_surplus(self):
        def prediction(edge, chance):
            return Prediction(10 + edge, edge, chance, 3.0, 0.0, [Slot("is_home", "Home", 1, 1, edge, edge)])

        bigger_edge = RankedPlayer(blank_row("Bigger edge", 10, 12, 1), prediction(2.0, 0.55), 1.10)
        higher_score = RankedPlayer(blank_row("Higher score", 10, 12, 0), prediction(1.5, 0.90), 1.35)
        ordered = sorted(
            [bigger_edge, higher_score],
            key=lambda item: (-item.score, -item.prediction.edge, item.row.name),
        )
        self.assertEqual(ordered[0].row.name, "Higher score")

    def test_board_keeps_positive_surplus_above_the_minimum_line(self):
        train = [blank_row(f"home-{index}", 10.0, 14.0, 1) for index in range(30)]
        train += [blank_row(f"away-{index}", 10.0, 10.0, 0) for index in range(30)]
        for index, item in enumerate(train):
            item.week = 1 + index % 5
        model = fit_model(train, alpha=0.2)
        week = [
            blank_row("Home starter", 12.0, 16.0, 1),
            blank_row("Away starter", 12.0, 12.0, 0),
            blank_row("Low line", 4.0, 9.0, 1),
        ]
        ranked = rank_week(week, model, min_projection=6.0, top_n=25)
        names = [item.row.name for item in ranked]
        self.assertIn("Home starter", names)
        self.assertNotIn("Low line", names)
        self.assertTrue(all(item.prediction.edge > 0 for item in ranked))
        self.assertTrue(all(item.row.values["projection"] >= 6 for item in ranked))
        self.assertAlmostEqual(ranked[0].score, ranked[0].prediction.p_beat * ranked[0].prediction.edge)


if __name__ == "__main__":
    unittest.main()
