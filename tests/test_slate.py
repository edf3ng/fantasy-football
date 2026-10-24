import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from overline.slate import _stat_row, load_cache, sample_logs


class SlateTest(unittest.TestCase):
    def test_sample_names_are_not_presented_as_clubs(self):
        logs = sample_logs()
        self.assertTrue(all(log.team in {"NOR", "SOU", "EAS", "WES"} for log in logs))
        self.assertGreater(len(logs), 100)

    def test_home_neutral_and_preseason_filters(self):
        base = {
            "season_type": "REG",
            "position": "WR",
            "season": "2024",
            "week": "3",
            "recent_team": "KC",
            "player_id": "00-1",
            "player_display_name": "A Player",
            "opponent_team": "LV",
            "fantasy_points_ppr": "18.5",
            "targets": "8",
            "carries": "1",
        }
        weekly = dict(base)
        weekly.pop("recent_team")
        weekly["team"] = "KC"
        weekly["passing_interceptions"] = "1"
        weekly["fantasy_points_ppr"] = ""
        weekly["passing_yards"] = "0"
        counted = _stat_row(weekly, {(2024, 3, "KC")}, {}, set())
        self.assertEqual(counted.team, "KC")
        self.assertAlmostEqual(counted.points, -2.0)

        home = _stat_row(base, {(2024, 3, "KC")}, {}, set())
        self.assertEqual(home.site, "home")
        self.assertEqual(home.is_home, 1)
        self.assertAlmostEqual(home.points, 18.5)

        neutral = _stat_row(base, set(), {}, {(2024, 3, "KC")})
        self.assertEqual(neutral.site, "neutral")
        self.assertEqual(neutral.is_home, 0)

        preseason = dict(base, season_type="PRE")
        self.assertIsNone(_stat_row(preseason, {(2024, 3, "KC")}, {}, set()))

        old = dict(base, season="2021")
        self.assertIsNone(_stat_row(old, set(), {}, set()))

    def test_cache_roundtrip(self):
        import tempfile

        from overline.slate import CACHE_FIELDS
        import csv

        log = sample_logs()[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logs.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CACHE_FIELDS)
                writer.writeheader()
                writer.writerow(
                    {
                        "player_id": log.player_id,
                        "name": log.name,
                        "position": log.position,
                        "team": log.team,
                        "season": log.season,
                        "week": log.week,
                        "points": log.points,
                        "targets": log.targets,
                        "carries": log.carries,
                        "opponent": log.opponent,
                        "is_home": log.is_home,
                        "site": log.site,
                    }
                )
            loaded = load_cache(path)
        self.assertEqual(loaded[0].player_id, log.player_id)
        self.assertEqual(loaded[0].site, log.site)
        self.assertAlmostEqual(loaded[0].points, log.points)


if __name__ == "__main__":
    unittest.main()
