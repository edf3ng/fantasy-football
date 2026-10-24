"""PPR points from counting stats.

nflverse files already carry fantasy_points_ppr. This module is the fallback
and the definition used in tests: 0.04 per passing yard, 4 per passing
touchdown, −2 per interception, 0.1 per rushing or receiving yard, 6 per
rushing or receiving touchdown, 1 per reception, −2 per fumble lost.
"""

from __future__ import annotations

STAT_WEIGHTS = {
    "passing_yards": 0.04,
    "passing_tds": 4.0,
    "interceptions": -2.0,
    "rushing_yards": 0.1,
    "rushing_tds": 6.0,
    "rushing_fumbles_lost": -2.0,
    "receptions": 1.0,
    "receiving_yards": 0.1,
    "receiving_tds": 6.0,
    "receiving_fumbles_lost": -2.0,
}


def ppr_points(row: dict) -> float:
    """Return PPR points for one stat row. Missing stats count as zero."""
    total = 0.0
    for stat, weight in STAT_WEIGHTS.items():
        total += _number(row.get(stat)) * weight
    return total


def _number(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number:
        return 0.0
    return number
