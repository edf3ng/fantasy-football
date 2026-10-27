import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from overline.features import GameLog, build_upcoming_rows
from overline.upcoming import candidate_shells, predict_upcoming, unplayed_kickoffs


def played(week, points, team="DAL", opponent="NYG", player_id="qb-dal", name="QB DAL 1"):
    return GameLog(
        player_id=player_id,
        name=name,
        position="QB",
        team=team,
        season=2026,
        week=week,
        points=points,
        targets=0,
        carries=3,
        opponent=opponent,
        is_home=1,
        site="home",
    )


def game(gameday, home, away, home_score="", away_score="", week=7):
    return {
        "game_type": "REG",
        "season": "2026",
        "week": str(week),
        "gameday": gameday,
        "gametime": "20:15",
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "location": "Home",
    }


class UpcomingTest(unittest.TestCase):
    def test_finished_games_drop_off_and_later_games_stay(self):
        rows = [
            game("2026-10-25", "NO", "PIT", "10", "16"),
            game("2026-10-26", "PHI", "DAL"),
            game("2026-11-20", "GB", "CAR", week=10),
        ]
        kickoffs = unplayed_kickoffs(rows, date(2026, 10, 26), 21)
        self.assertEqual([(kick.away, kick.home) for kick in kickoffs], [("DAL", "PHI")])

    def test_shells_are_recent_players_on_the_teams_playing(self):
        logs = [
            played(5, 12),
            played(6, 18),
            played(6, 9, team="NYG", player_id="qb-nyg", name="QB NYG 1"),
            played(3, 20, team="PHI", player_id="old-phi", name="Old PHI"),
        ]
        kickoffs = unplayed_kickoffs([game("2026-10-26", "PHI", "DAL")], date(2026, 10, 26), 7)
        shells = candidate_shells(logs, kickoffs)
        names = {shell.name for shell in shells}
        self.assertIn("QB DAL 1", names)
        self.assertNotIn("QB NYG 1", names)
        self.assertNotIn("Old PHI", names)
        later = unplayed_kickoffs([game("2026-11-15", "GB", "DAL", week=10)], date(2026, 10, 26), 21)
        later_names = {shell.name for shell in candidate_shells(logs, later)}
        self.assertIn("QB DAL 1", later_names)
        dal = next(shell for shell in shells if shell.name == "QB DAL 1")
        self.assertEqual(dal.opponent, "PHI")
        self.assertEqual(dal.site, "away")
        self.assertEqual(dal.week, 7)

    def test_upcoming_row_has_no_result_and_ignores_its_own_placeholder(self):
        logs = [played(5, 10, opponent="PHI"), played(6, 20, opponent="PHI")]
        shell = GameLog(
            "qb-dal",
            "QB DAL 1",
            "QB",
            "DAL",
            2026,
            7,
            99,
            0,
            0,
            "PHI",
            0,
            "away",
            "2026-10-26",
            "20:15",
        )
        rows = build_upcoming_rows(logs, [shell])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].actual)
        self.assertAlmostEqual(rows[0].values["last_points"], 20.0)
        self.assertLess(rows[0].values["projection"], 20.0)

    def test_predict_board_is_the_unplayed_game(self):
        logs = [played(5, 16, opponent="NYG"), played(6, 18, opponent="WAS")]
        logs += [played(5, 14, team="PHI", opponent="DAL", player_id="qb-phi", name="QB PHI 1")]
        logs += [played(6, 15, team="PHI", opponent="NYG", player_id="qb-phi", name="QB PHI 1")]
        schedule = [game("2026-10-26", "PHI", "DAL"), game("2026-10-25", "NO", "PIT", "10", "16")]
        payload = predict_upcoming(
            logs, schedule, today=date(2026, 10, 26), horizon_days=3, min_projection=0, min_train=1
        )
        self.assertTrue(payload["weeks"][0]["label"].startswith("Tonight"))
        self.assertEqual(payload["weeks"][0]["matchups"], ["DAL at PHI"])
        self.assertGreaterEqual(payload["weeks"][0]["slate"], 2)
        self.assertTrue(all(player["actual"] is None for player in payload["weeks"][0]["players"]))


if __name__ == "__main__":
    unittest.main()
