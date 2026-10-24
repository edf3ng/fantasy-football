import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from overline.features import CONTEXT_FEATURES, GameLog, build_feature_rows


def game(week, points, team="AAA", opp="BBB", position="WR", player_id="p1", season=2024):
    return GameLog(
        player_id=player_id,
        name=f"{position} {team} 1",
        position=position,
        team=team,
        season=season,
        week=week,
        points=points,
        targets=8,
        carries=1,
        opponent=opp,
        is_home=1,
        site="home",
    )


class FeatureTest(unittest.TestCase):
    def test_first_career_game_has_no_line(self):
        rows = build_feature_rows([game(1, 10)])
        self.assertEqual(rows, [])

    def test_opponent_window_ignores_the_current_week(self):
        rows = build_feature_rows([game(1, 10.0), game(2, 50.0)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].week, 2)
        self.assertAlmostEqual(rows[0].values["opp_pts_allowed"], 10.0)
        self.assertAlmostEqual(rows[0].values["projection"], 10.0)

    def test_later_box_scores_do_not_change_this_week(self):
        logs = [game(week, 12.0 + week, season=season) for season in (2024, 2025) for week in range(1, 8)]
        target = (2025, 4)
        base = {
            (row.season, row.week): dict(row.values)
            for row in build_feature_rows(logs)
            if (row.season, row.week) <= target
        }
        mutated = [
            replace(item, points=item.points + 40, targets=item.targets + 5)
            if (item.season, item.week) >= target
            else item
            for item in logs
        ]
        altered = {
            (row.season, row.week): row.values
            for row in build_feature_rows(mutated)
            if (row.season, row.week) <= target
        }
        self.assertEqual(base.keys(), altered.keys())
        for key, values in base.items():
            for feature in list(CONTEXT_FEATURES) + ["projection"]:
                self.assertAlmostEqual(values[feature], altered[key][feature], msg=feature)


if __name__ == "__main__":
    unittest.main()
