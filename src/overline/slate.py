"""Sample league and the nflverse cache that feeds the board."""

from __future__ import annotations

import csv
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

from overline.features import POSITIONS, GameLog
from overline.scoring import ppr_points

WEEKLY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv"
)
GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
FIRST_SEASON = 2023
CACHE_FIELDS = (
    "player_id",
    "name",
    "position",
    "team",
    "season",
    "week",
    "points",
    "targets",
    "carries",
    "opponent",
    "is_home",
    "site",
)


def schedule_path() -> Path:
    return cache_path().with_name("schedule.csv")


def cache_path() -> Path:
    override = os.environ.get("OVERLINE_CACHE")
    if override:
        return Path(override)
    package = Path(__file__).resolve()
    repo = package.parents[2]
    if (repo / "pyproject.toml").exists():
        return repo / "data" / "cache" / "logs.csv"
    return Path.cwd() / "data" / "cache" / "logs.csv"


def sample_logs() -> list[GameLog]:
    """Synthetic four-team league. Names are not NFL players.

    Home games score about 3 PPR more than the player's skill. The form line
    never sees site, so the surplus model has a real signal to find.
    """
    rng = random.Random(7)
    skill = {"QB": 16.0, "RB": 12.0, "WR": 11.0, "TE": 8.0}
    usage = {
        "QB": (0.2, 4.0),
        "RB": (3.0, 14.0),
        "WR": (7.0, 0.4),
        "TE": (5.0, 0.2),
    }
    teams = ("NOR", "SOU", "EAS", "WES")
    roster = ("QB", "RB", "RB", "WR", "WR", "TE")
    players = []
    for team in teams:
        for index, position in enumerate(roster):
            players.append(
                {
                    "player_id": f"{team}-{position}-{index}",
                    "name": f"{position} {team} {index + 1}",
                    "position": position,
                    "team": team,
                    "skill": skill[position] + (index % 2) * 2.5,
                    "targets": usage[position][0],
                    "carries": usage[position][1],
                }
            )
    logs: list[GameLog] = []
    for season in (2024, 2025):
        for week in range(1, 7):
            pairs = [("NOR", "SOU"), ("EAS", "WES")]
            if week % 2 == 0:
                pairs = [(away, home) for home, away in pairs]
            playing = {}
            for home, away in pairs:
                playing[home] = (away, 1, "home")
                playing[away] = (home, 0, "away")
            for player in players:
                opponent, is_home, site = playing[player["team"]]
                points = player["skill"] + (3.0 if is_home else 0.0) + rng.uniform(-0.4, 0.4)
                logs.append(
                    GameLog(
                        player_id=player["player_id"],
                        name=player["name"],
                        position=player["position"],
                        team=player["team"],
                        season=season,
                        week=week,
                        points=max(0.0, points),
                        targets=player["targets"],
                        carries=player["carries"],
                        opponent=opponent,
                        is_home=is_home,
                        site=site,
                    )
                )
    return logs


def load_cache(path: Path | None = None) -> list[GameLog]:
    file_path = path or cache_path()
    logs = []
    with file_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            logs.append(
                GameLog(
                    player_id=row["player_id"],
                    name=row["name"],
                    position=row["position"],
                    team=row["team"],
                    season=int(row["season"]),
                    week=int(row["week"]),
                    points=float(row["points"]),
                    targets=float(row["targets"]),
                    carries=float(row["carries"]),
                    opponent=row["opponent"],
                    is_home=int(row["is_home"]),
                    site=row["site"],
                )
            )
    return logs


def fetch_schedule(path: Path | None = None, refresh: bool = False) -> Path:
    """Save the nflverse schedule, including games that do not have a score yet."""
    file_path = path or schedule_path()
    if file_path.exists() and not refresh:
        return file_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = file_path.with_suffix(".csv.partial")
    with urllib.request.urlopen(_request(GAMES_URL), timeout=120) as response:
        temporary.write_bytes(response.read())
    temporary.replace(file_path)
    return file_path


def load_schedule(path: Path | None = None) -> list[dict]:
    file_path = path or schedule_path()
    with file_path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def refresh_caches(max_age_seconds: int = 180) -> None:
    """Download stats and the schedule when the cache is older than max_age_seconds."""
    logs_path = cache_path()
    games_path = schedule_path()
    logs_stale = not logs_path.exists() or _age_seconds(logs_path) > max_age_seconds
    games_stale = not games_path.exists() or _age_seconds(games_path) > max_age_seconds
    if logs_stale:
        fetch_logs(refresh=True)
    elif games_stale:
        fetch_schedule(refresh=True)


def _age_seconds(path: Path) -> float:
    return max(0.0, time.time() - path.stat().st_mtime)


def fetch_logs(path: Path | None = None, refresh: bool = False) -> Path:
    """Download nflverse stats and schedules into a compact cache.

    Keeps regular-season QB, RB, WR, and TE games from FIRST_SEASON forward.
    """
    file_path = path or cache_path()
    if file_path.exists() and not refresh:
        return file_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fetch_schedule(refresh=refresh)
    home_teams, opponents, neutral = _schedule(schedule_path())
    temporary = file_path.with_suffix(".csv.partial")
    kept = 0
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CACHE_FIELDS)
        writer.writeheader()
        for season in range(FIRST_SEASON, FIRST_SEASON + 8):
            try:
                response = urllib.request.urlopen(_request(WEEKLY_URL.format(season=season)), timeout=180)
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and kept:
                    break
                if exc.code == 404:
                    continue
                raise
            with response:
                text = (line.decode("utf-8") for line in response)
                for row in csv.DictReader(text):
                    log = _stat_row(row, home_teams, opponents, neutral)
                    if log is None:
                        continue
                    writer.writerow(
                        {
                            "player_id": log.player_id,
                            "name": log.name,
                            "position": log.position,
                            "team": log.team,
                            "season": log.season,
                            "week": log.week,
                            "points": f"{log.points:.4f}",
                            "targets": f"{log.targets:.4f}",
                            "carries": f"{log.carries:.4f}",
                            "opponent": log.opponent,
                            "is_home": log.is_home,
                            "site": log.site,
                        }
                    )
                    kept += 1
    if kept == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("nflverse response did not include any skill-position games")
    temporary.replace(file_path)
    return file_path


def _schedule(
    path: Path | None = None,
) -> tuple[set[tuple[int, int, str]], dict[tuple[int, int, str], str], set[tuple[int, int, str]]]:
    home_teams: set[tuple[int, int, str]] = set()
    opponents: dict[tuple[int, int, str], str] = {}
    neutral: set[tuple[int, int, str]] = set()
    with (path or schedule_path()).open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("game_type") not in ("REG", ""):
                continue
            season = _int(row.get("season"))
            week = _int(row.get("week"))
            if season < FIRST_SEASON or week < 1 or week > 18:
                continue
            home = row.get("home_team") or ""
            away = row.get("away_team") or ""
            if not home or not away:
                continue
            opponents[(season, week, home)] = away
            opponents[(season, week, away)] = home
            if (row.get("location") or "").lower() == "neutral":
                neutral.add((season, week, home))
                neutral.add((season, week, away))
            else:
                home_teams.add((season, week, home))
    return home_teams, opponents, neutral


def _stat_row(row: dict, home_teams: set, opponents: dict, neutral: set) -> GameLog | None:
    if row.get("season_type") not in ("REG", ""):
        return None
    position = row.get("position") or ""
    if position not in POSITIONS:
        return None
    season = _int(row.get("season"))
    week = _int(row.get("week"))
    if season < FIRST_SEASON or week < 1 or week > 18:
        return None
    team = row.get("recent_team") or row.get("team") or ""
    player_id = row.get("player_id") or ""
    if not team or not player_id:
        return None
    key = (season, week, team)
    opponent = row.get("opponent_team") or opponents.get(key, "")
    if not opponent:
        return None
    if key in neutral:
        is_home, site = 0, "neutral"
    elif key in home_teams:
        is_home, site = 1, "home"
    else:
        is_home, site = 0, "away"
    raw_points = row.get("fantasy_points_ppr")
    if raw_points not in (None, ""):
        points = _float(raw_points)
    else:
        counting = dict(row)
        if not counting.get("interceptions"):
            counting["interceptions"] = counting.get("passing_interceptions")
        points = ppr_points(counting)
    name = row.get("player_display_name") or row.get("player_name") or player_id
    return GameLog(
        player_id=player_id,
        name=name,
        position=position,
        team=team,
        season=season,
        week=week,
        points=points,
        targets=_float(row.get("targets")),
        carries=_float(row.get("carries")),
        opponent=opponent,
        is_home=is_home,
        site=site,
    )


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": "overline"})


def _int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return -1


def _float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number:
        return 0.0
    return number
