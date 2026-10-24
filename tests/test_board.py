import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from overline.board import assemble
from overline.slate import sample_logs
from overline.web import render_page


class BoardTest(unittest.TestCase):
    def test_walk_forward_board_and_context_window(self):
        payload = assemble(sample_logs(), source="sample", note="Sample slate.")
        self.assertGreaterEqual(len(payload["weeks"]), 1)
        last = payload["weeks"][-1]
        self.assertGreaterEqual(len(last["players"]), 8)
        home = 0
        for player in last["players"]:
            self.assertGreater(player["edge"], 0.0)
            self.assertGreater(player["p_beat"], 0.5)
            self.assertEqual(len(player["slots"]), 9)
            self.assertAlmostEqual(player["pull_sum"], player["edge"], places=6)
            if any(slot["feature"] == "is_home" and slot["raw"] == 1.0 for slot in player["slots"]):
                home += 1
        self.assertGreaterEqual(home, int(0.8 * len(last["players"])))

    def test_target_week_results_do_not_change_the_fit(self):
        logs = sample_logs()
        base = assemble(logs, source="sample", note="sample")
        mutated = [
            replace(log, points=log.points + 25)
            if log.season == 2025 and log.week == 6
            else log
            for log in logs
        ]
        altered = assemble(mutated, source="sample", note="sample")
        base_week = next(week for week in base["weeks"] if week["season"] == 2025 and week["week"] == 6)
        altered_week = next(week for week in altered["weeks"] if week["season"] == 2025 and week["week"] == 6)
        base_edges = {player["player_id"]: player["edge"] for player in base_week["players"]}
        altered_edges = {player["player_id"]: player["edge"] for player in altered_week["players"]}
        self.assertEqual(base_edges.keys(), altered_edges.keys())
        for player_id, edge in base_edges.items():
            self.assertAlmostEqual(edge, altered_edges[player_id], places=6)

    def test_page_shows_the_context_window(self):
        payload = assemble(sample_logs(), source="sample", note="Sample slate.")
        page = render_page(payload)
        self.assertIn("Context window", page)
        self.assertIn(payload["weeks"][-1]["players"][0]["name"], page)
        self.assertIn("Sample slate.", page)


if __name__ == "__main__":
    unittest.main()
