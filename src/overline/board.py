"""Walk-forward weekly boards."""

from __future__ import annotations

from overline.features import FeatureRow, build_feature_rows
from overline.model import fit_model
from overline.rank import MIN_PROJECTION, TOP_N, rank_week

MIN_TRAIN = 60
# A full skill-position slate is a few hundred players. Fewer than this means
# the week is still being posted, so it should not be the week the board opens on.
FULL_SLATE = 250


def assemble(
    logs: list,
    source: str,
    note: str,
    min_projection: float = MIN_PROJECTION,
    top_n: int = TOP_N,
    min_train: int = MIN_TRAIN,
) -> dict:
    """Fit each week on earlier weeks and keep the players expected to clear the line."""
    rows = build_feature_rows(logs)
    order: list[tuple[int, int]] = []
    buckets: dict[tuple[int, int], list[FeatureRow]] = {}
    for row in rows:
        key = (row.season, row.week)
        if key not in buckets:
            order.append(key)
            buckets[key] = []
        buckets[key].append(row)

    train: list[FeatureRow] = []
    weeks = []
    for key in order:
        week_rows = buckets[key]
        if len(train) >= min_train:
            model = fit_model(train)
            ranked = rank_week(week_rows, model, min_projection=min_projection, top_n=top_n)
            eligible = [row for row in week_rows if row.values["projection"] >= min_projection]
            hits = sum(1 for item in ranked if item.row.actual > item.row.values["projection"])
            eligible_hits = sum(1 for row in eligible if row.actual > row.values["projection"])
            weeks.append(
                {
                    "season": key[0],
                    "week": key[1],
                    "slate": len(week_rows),
                    "eligible": len(eligible),
                    "eligible_hits": eligible_hits,
                    "hits": hits,
                    "players": [_player(item) for item in ranked],
                }
            )
        train.extend(week_rows)

    saw_full_slate = any(week["slate"] >= FULL_SLATE for week in weeks)
    for week in weeks:
        week["partial"] = saw_full_slate and week["slate"] < FULL_SLATE
    featured = len(weeks) - 1 if weeks else 0
    for index, week in enumerate(weeks):
        if not week["partial"]:
            featured = index
    return {
        "source": source,
        "note": note,
        "min_projection": min_projection,
        "featured": featured,
        "weeks": weeks,
    }


def _player(item) -> dict:
    row = item.row
    prediction = item.prediction
    pull_sum = prediction.intercept + sum(slot.pull for slot in prediction.slots)
    return {
        "player_id": row.player_id,
        "name": row.name,
        "position": row.position,
        "team": row.team,
        "opponent": row.opponent,
        "site": row.site,
        "projection": row.values["projection"],
        "expected": prediction.expected,
        "edge": prediction.edge,
        "p_beat": prediction.p_beat,
        "score": item.score,
        "sigma": prediction.sigma,
        "actual": row.actual,
        "beat": row.actual > row.values["projection"],
        "intercept": prediction.intercept,
        "pull_sum": pull_sum,
        "line": {
            "projection": row.values["projection"],
            "last_points": row.values["last_points"],
            "avg_3": row.values["avg_3"],
            "season_avg": row.values["season_avg"],
            "games_played": row.values["games_played"],
        },
        "slots": [
            {
                "feature": slot.feature,
                "label": slot.label,
                "raw": slot.raw,
                "scaled": slot.scaled,
                "weight": slot.weight,
                "pull": slot.pull,
            }
            for slot in prediction.slots
        ],
    }
