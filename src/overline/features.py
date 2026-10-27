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
    gameday: str = ""
    gametime: str = ""


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
    actual: float | None
    values: dict


def build_feature_rows(logs: list[GameLog]) -> list[FeatureRow]:
    """One row per player-week that has at least one earlier game.

    Opponent points allowed and the form line for week t ignore week t and
    every later week. Callers can edit those later box scores and the earlier
    context windows stay put.
    """
    state, weeks, weekly_allowed = _index_played(logs)
    rows: list[FeatureRow] = []
    for season, week, games in weeks:
        for game in games:
            values = _feature_values(state, game)
            if values is None:
                continue
            rows.append(_row(game, values, game.points))
        _fold_week(state, season, week, games, weekly_allowed)
    return rows


def build_upcoming_rows(played: list[GameLog], shells: list[GameLog]) -> list[FeatureRow]:
    """Context for games that have not been played.

    The history includes every completed game, including earlier games in the
    same week. The shells themselves are not folded in, so a Monday game does
    not pretend it already has a box score.
    """
    state, weeks, weekly_allowed = _index_played(played)
    for season, week, games in weeks:
        _fold_week(state, season, week, games, weekly_allowed)
    rows: list[FeatureRow] = []
    for shell in shells:
        values = _feature_values(state, shell)
        if values is None:
            continue
        rows.append(_row(shell, values, None))
    return rows


class _History:
    def __init__(self) -> None:
        self.player: dict[str, list[tuple[int, float, float, float]]] = {}
        self.defense: dict[tuple[str, str], list[float]] = {}
        self.pos_sum = {position: 0.0 for position in POSITIONS}
        self.pos_count = {position: 0 for position in POSITIONS}
        self.allowed_sum = {position: 0.0 for position in POSITIONS}
        self.allowed_count = {position: 0 for position in POSITIONS}


def _index_played(
    logs: list[GameLog],
) -> tuple[_History, list[tuple[int, int, list[GameLog]]], dict[tuple[int, int, str, str], float]]:
    ordered = sorted(logs, key=lambda game: (game.season, game.week, game.player_id))
    by_week: dict[tuple[int, int], list[GameLog]] = {}
    weekly_allowed: dict[tuple[int, int, str, str], float] = {}
    for game in ordered:
        by_week.setdefault((game.season, game.week), []).append(game)
        if game.opponent and game.position in POSITIONS:
            key = (game.season, game.week, game.opponent, game.position)
            weekly_allowed[key] = weekly_allowed.get(key, 0.0) + game.points
    weeks = [(season, week, by_week[(season, week)]) for season, week in sorted(by_week)]
    return _History(), weeks, weekly_allowed


def _feature_values(state: _History, game: GameLog) -> dict | None:
    if game.position not in POSITIONS:
        return None
    prior = state.player.get(game.player_id, [])
    if not prior:
        return None
    position_mean = {
        position: (state.pos_sum[position] / state.pos_count[position]) if state.pos_count[position] else 0.0
        for position in POSITIONS
    }
    allowed_mean = {
        position: (state.allowed_sum[position] / state.allowed_count[position])
        if state.allowed_count[position]
        else position_mean[position]
        for position in POSITIONS
    }
    prior_points = [item[1] for item in prior]
    season_points = [item[1] for item in prior if item[0] == game.season]
    mean = position_mean[game.position]
    last_three = prior[-3:]
    avg_3 = _mean([item[1] for item in last_three])
    season_avg = _mean(season_points) if season_points else _mean(prior_points)
    defense = state.defense.get((game.opponent, game.position), [])
    recent_defense = defense[-8:]
    return {
        "projection": form_line(prior_points, mean),
        "last_points": prior_points[-1],
        "avg_3": avg_3,
        "season_avg": season_avg,
        "trend": avg_3 - season_avg,
        "games_played": float(len(season_points)),
        "targets_avg_3": _mean([item[2] for item in last_three]),
        "carries_avg_3": _mean([item[3] for item in last_three]),
        "is_home": float(game.is_home),
        "opp_pts_allowed": _mean(recent_defense) if recent_defense else allowed_mean[game.position],
        "pos_qb": 1.0 if game.position == "QB" else 0.0,
        "pos_rb": 1.0 if game.position == "RB" else 0.0,
        "pos_wr": 1.0 if game.position == "WR" else 0.0,
        "pos_te": 1.0 if game.position == "TE" else 0.0,
    }


def _row(game: GameLog, values: dict, actual: float | None) -> FeatureRow:
    return FeatureRow(
        player_id=game.player_id,
        name=game.name,
        position=game.position,
        team=game.team,
        opponent=game.opponent,
        site=game.site,
        season=game.season,
        week=game.week,
        actual=actual,
        values=values,
    )


def _fold_week(
    state: _History,
    season: int,
    week: int,
    games: list[GameLog],
    weekly_allowed: dict[tuple[int, int, str, str], float],
) -> None:
    seen_defenses = set()
    for game in games:
        if game.position not in POSITIONS:
            continue
        state.player.setdefault(game.player_id, []).append((season, game.points, game.targets, game.carries))
        state.pos_sum[game.position] += game.points
        state.pos_count[game.position] += 1
        if not game.opponent:
            continue
        marker = (season, week, game.opponent, game.position)
        if marker in seen_defenses:
            continue
        seen_defenses.add(marker)
        allowed = weekly_allowed.get(marker, 0.0)
        state.defense.setdefault((game.opponent, game.position), []).append(allowed)
        state.allowed_sum[game.position] += allowed
        state.allowed_count[game.position] += 1


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))
