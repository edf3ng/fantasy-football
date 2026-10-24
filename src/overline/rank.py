"""Keep players the model expects to finish above their line."""

from __future__ import annotations

from dataclasses import dataclass

from overline.features import FeatureRow
from overline.model import FittedModel, Prediction, predict

MIN_PROJECTION = 6.0
TOP_N = 25


@dataclass
class RankedPlayer:
    row: FeatureRow
    prediction: Prediction
    score: float


def rank_week(
    rows: list[FeatureRow],
    model: FittedModel,
    min_projection: float = MIN_PROJECTION,
    top_n: int = TOP_N,
) -> list[RankedPlayer]:
    """Rank players with a positive surplus and a line of at least min_projection.

    Score is P(actual > line) times the surplus. Ties break toward the larger
    surplus, then the player name.
    """
    ranked: list[RankedPlayer] = []
    for row in rows:
        if row.values["projection"] < min_projection:
            continue
        prediction = predict(model, row)
        if prediction.edge <= 0.0:
            continue
        ranked.append(
            RankedPlayer(
                row=row,
                prediction=prediction,
                score=prediction.p_beat * prediction.edge,
            )
        )
    ranked.sort(key=lambda item: (-item.score, -item.prediction.edge, item.row.name))
    return ranked[:top_n]
