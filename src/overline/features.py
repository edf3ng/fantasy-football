"""Context windows built only from games before the target week."""

from __future__ import annotations

from dataclasses import dataclass

from overline.projections import form_line

POSITIONS = ("QB", "RB", "WR", "TE")

# Model inputs, in context-window order. Tight end is the reference position
# (all three indicators zero), so these columns are not a copy of the intercept.
CONTEXT_FEATURES = (
    "trend",
    "games_played",
    "targets_avg_3",
    "carries_avg_3",
    "is_home",
    "opp_pts_allowed",
    "pos_qb",
    "pos_rb",
    "pos_wr",
)

CONTEXT_LABELS = {
    "trend": "Recent trend",
    "games_played": "Games this season",
    "targets_avg_3": "Targets, last three",
    "carries_avg_3": "Carries, last three",
    "is_home": "Home",
    "opp_pts_allowed": "Opponent allowed",
    "pos_qb": "Quarterback",
    "pos_rb": "Running back",
    "pos_wr": "Wide receiver",
}


@dataclass
class GameLog:
    player_id: str
    name: str
    position: str
    team: str
    season: int
    week: int
    points: float
    targets: float
    carries: float
    opponent: str
    is_home: int
    site: str


@dataclass
class FeatureRow:
    player_id: str
    name: str
    position: str
    team: str
    opponent: str
    site: str
    season: int
    week: int
    actual: float
    values: dict


def build_feature_rows(logs: list[GameLog]) -> list[FeatureRow]:
    """One row per player-week that has at least one earlier game.

    Opponent points allowed and the form line for week t ignore week t and
    every later week. Callers can edit those later box scores and the earlier
    context windows stay put.
    """
    ordered = sorted(logs, key=lambda game: (game.season, game.week, game.player_id))
    by_week: dict[tuple[int, int], list[GameLog]] = {}
    weekly_allowed: dict[tuple[int, int, str, str], float] = {}
    for game in ordered:
        by_week.setdefault((game.season, game.week), []).append(game)
        if game.opponent:
            key = (game.season, game.week, game.opponent, game.position)
            weekly_allowed[key] = weekly_allowed.get(key, 0.0) + game.points

    history: dict[str, list[tuple[int, float, float, float]]] = {}
    defense_hist: dict[tuple[str, str], list[float]] = {}
    pos_sum = {position: 0.0 for position in POSITIONS}
    pos_count = {position: 0 for position in POSITIONS}
    allowed_sum = {position: 0.0 for position in POSITIONS}
    allowed_count = {position: 0 for position in POSITIONS}
    rows: list[FeatureRow] = []

    for season, week in sorted(by_week):
        games = by_week[(season, week)]
        position_mean = {
            position: (pos_sum[position] / pos_count[position]) if pos_count[position] else 0.0
            for position in POSITIONS
        }
        allowed_mean = {
            position: (allowed_sum[position] / allowed_count[position])
            if allowed_count[position]
            else position_mean[position]
            for position in POSITIONS
        }

        for game in games:
            if game.position not in POSITIONS:
                continue
            prior = history.get(game.player_id, [])
            if not prior:
                continue
            prior_points = [item[1] for item in prior]
            season_points = [item[1] for item in prior if item[0] == season]
            mean = position_mean[game.position]
            last_three = prior[-3:]
            avg_3 = _mean([item[1] for item in last_three])
            season_avg = _mean(season_points) if season_points else _mean(prior_points)
            defense = defense_hist.get((game.opponent, game.position), [])
            recent_defense = defense[-8:]
            values = {
                "projection": form_line(prior_points, mean),
                "last_points": prior_points[-1],
                "avg_3": avg_3,
                "season_avg": season_avg,
                "trend": avg_3 - season_avg,
                "games_played": float(len(season_points)),
                "targets_avg_3": _mean([item[2] for item in last_three]),
                "carries_avg_3": _mean([item[3] for item in last_three]),
                "is_home": float(game.is_home),
                "opp_pts_allowed": _mean(recent_defense)
                if recent_defense
                else allowed_mean[game.position],
                "pos_qb": 1.0 if game.position == "QB" else 0.0,
                "pos_rb": 1.0 if game.position == "RB" else 0.0,
                "pos_wr": 1.0 if game.position == "WR" else 0.0,
                "pos_te": 1.0 if game.position == "TE" else 0.0,
            }
            rows.append(
                FeatureRow(
                    player_id=game.player_id,
                    name=game.name,
                    position=game.position,
                    team=game.team,
                    opponent=game.opponent,
                    site=game.site,
                    season=season,
                    week=week,
                    actual=game.points,
                    values=values,
                )
            )

        seen_defenses = set()
        for game in games:
            if game.position not in POSITIONS:
                continue
            history.setdefault(game.player_id, []).append(
                (season, game.points, game.targets, game.carries)
            )
            pos_sum[game.position] += game.points
            pos_count[game.position] += 1
            if not game.opponent:
                continue
            marker = (season, week, game.opponent, game.position)
            if marker in seen_defenses:
                continue
            seen_defenses.add(marker)
            allowed = weekly_allowed.get(marker, 0.0)
            defense_hist.setdefault((game.opponent, game.position), []).append(allowed)
            allowed_sum[game.position] += allowed
            allowed_count[game.position] += 1

    return rows


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))
