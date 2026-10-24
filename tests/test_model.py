import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from overline.features import CONTEXT_FEATURES, FeatureRow
from overline.model import fit_model, predict


def row(name, is_home, actual, projection=10.0):
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
        week=6,
        actual=actual,
        values=values,
    )


class ModelTest(unittest.TestCase):
    def test_home_surplus_and_window_identity(self):
        train = [row(f"home-{index}", 1, 13.0) for index in range(40)]
        train += [row(f"away-{index}", 0, 10.0) for index in range(40)]
        model = fit_model(train, alpha=0.2)
        home = predict(model, row("Home WR", 1, 13.0))
        away = predict(model, row("Away WR", 0, 10.0))
        self.assertGreater(home.edge, 2.0)
        self.assertLess(abs(away.edge), 0.5)
        self.assertGreater(home.p_beat, 0.5)
        self.assertAlmostEqual(home.intercept + sum(slot.pull for slot in home.slots), home.edge)
        self.assertEqual([slot.feature for slot in home.slots], list(CONTEXT_FEATURES))
        home_slot = next(slot for slot in home.slots if slot.feature == "is_home")
        self.assertGreater(home_slot.pull, 0.0)


if __name__ == "__main__":
    unittest.main()
