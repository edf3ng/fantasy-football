"""Predictions for games that do not have a score yet."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from overline.board import _player
from overline.features import GameLog, build_feature_rows, build_upcoming_rows
from overline.model import fit_model
from overline.rank import MIN_PROJECTION, TOP_N, rank_week

EASTERN = ZoneInfo("America/New_York")
LOOKBACK_WEEKS = 2
HORIZON_DAYS = 21
MIN_TRAIN = 60


@dataclass
class Kickoff:
    season: int
    week: int
    gameday: str
    gametime: str
    home: str
    away: str
    neutral: bool


def predict_upcoming(
    logs: list[GameLog],
    schedule_rows: list[dict],
    today: date | None = None,
    horizon_days: int = HORIZON_DAYS,
    min_projection: float = MIN_PROJECTION,
    top_n: int = TOP_N,
    min_train: int = MIN_TRAIN,
) -> dict:
    """Refit on completed games and rank players in each upcoming date."""
    current = today or datetime.now(EASTERN).date()
    kickoffs = unplayed_kickoffs(schedule_rows, current, horizon_days)
    shells = candidate_shells(logs, kickoffs)
    upcoming_rows = build_upcoming_rows(logs, shells)
    played_rows = build_feature_rows(logs)
    trained = _trained_through(logs)
    note = (
        f"Predictions for games without a score, from {current.strftime('%b')} {current.day}. "
        f"The model was refit on completed games through {trained}. "
        "A player is included when their latest game is for that team and within two weeks of the latest completed week. "
        "The form line is a shrunk average of earlier games, not a published consensus."
    )
    if len(played_rows) < min_train:
        return _payload(note, trained, current, [])
    model = fit_model(played_rows)
    by_day: dict[str, list] = {}
    for row in upcoming_rows:
        by_day.setdefault(_day_for(row, shells), []).append(row)
    kick_by_day: dict[str, list[Kickoff]] = {}
    order: list[str] = []
    for kick in kickoffs:
        kick_by_day.setdefault(kick.gameday, []).append(kick)
        if kick.gameday not in order:
            order.append(kick.gameday)
    weeks = []
    for day in order:
        day_rows = by_day.get(day, [])
        ranked = rank_week(day_rows, model, min_projection=min_projection, top_n=top_n)
        kicks = kick_by_day.get(day, [])
        matchups = [_matchup(kick) for kick in kicks]
        weeks.append(
            {
                "key": day + "|" + ",".join(matchups),
                "season": kicks[0].season if kicks else day_rows[0].season,
                "week": kicks[0].week if kicks else day_rows[0].week,
                "gameday": day,
                "label": _label(day, current, matchups),
                "kickoff": _kickoff_label(kicks),
                "matchups": matchups,
                "upcoming": True,
                "partial": False,
                "slate": len(day_rows),
                "eligible": sum(1 for row in day_rows if row.values["projection"] >= min_projection),
                "players": [_annotate(item, kicks) for item in ranked],
            }
        )
    return _payload(note, trained, current, weeks)


def unplayed_kickoffs(rows: list[dict], today: date, horizon_days: int) -> list[Kickoff]:
    """Regular-season games from today through the horizon that have no score."""
    last = today + timedelta(days=horizon_days)
    kickoffs: list[Kickoff] = []
    for row in rows:
        if (row.get("game_type") or "REG") not in ("REG", ""):
            continue
        gameday = row.get("gameday") or ""
        try:
            played_on = date.fromisoformat(gameday)
        except ValueError:
            continue
        if played_on < today or played_on > last:
            continue
        if not _blank_score(row.get("away_score")) or not _blank_score(row.get("home_score")):
            continue
        home = row.get("home_team") or ""
        away = row.get("away_team") or ""
        if not home or not away:
            continue
        try:
            season = int(row.get("season") or 0)
            week = int(row.get("week") or 0)
        except ValueError:
            continue
        kickoffs.append(
            Kickoff(
                season=season,
                week=week,
                gameday=gameday,
                gametime=(row.get("gametime") or "")[:5],
                home=home,
                away=away,
                neutral=(row.get("location") or "").lower() == "neutral",
            )
        )
    kickoffs.sort(key=lambda kick: (kick.gameday, kick.gametime, kick.away))
    return kickoffs


def candidate_shells(logs: list[GameLog], kickoffs: list[Kickoff]) -> list[GameLog]:
    """Players active for a team in the kickoff.

    Active means their latest game is within two weeks of the latest completed
    week, and they have not already played the kickoff week.
    """
    latest: dict[str, GameLog] = {}
    newest_week: dict[int, int] = {}
    for log in logs:
        previous = latest.get(log.player_id)
        if previous is None or (log.season, log.week) >= (previous.season, previous.week):
            latest[log.player_id] = log
        newest_week[log.season] = max(newest_week.get(log.season, 0), log.week)
    shells: list[GameLog] = []
    for kick in kickoffs:
        # Active means they played within two weeks of the latest completed week,
        # not within two weeks of a game that is still weeks away.
        active_since = newest_week.get(kick.season, kick.week) - LOOKBACK_WEEKS
        if kick.neutral:
            sides = ((kick.home, kick.away, 0, "neutral"), (kick.away, kick.home, 0, "neutral"))
        else:
            sides = ((kick.home, kick.away, 1, "home"), (kick.away, kick.home, 0, "away"))
        for team, opponent, is_home, site in sides:
            for player in latest.values():
                if player.team != team or player.season != kick.season:
                    continue
                if player.week >= kick.week or player.week < active_since:
                    continue
                shells.append(
                    GameLog(
                        player_id=player.player_id,
                        name=player.name,
                        position=player.position,
                        team=team,
                        season=kick.season,
                        week=kick.week,
                        points=0.0,
                        targets=0.0,
                        carries=0.0,
                        opponent=opponent,
                        is_home=is_home,
                        site=site,
                        gameday=kick.gameday,
                        gametime=kick.gametime,
                    )
                )
    return shells


def _annotate(item, kicks: list[Kickoff]) -> dict:
    player = _player(item)
    kick = next((item_kick for item_kick in kicks if item.row.team in (item_kick.home, item_kick.away)), None)
    player["kickoff"] = _format_time(kick.gametime) if kick else ""
    player["matchup"] = _matchup(kick) if kick else ""
    player["upcoming"] = True
    player["actual"] = None
    player["beat"] = None
    return player


def _payload(note: str, trained: str, current: date, weeks: list[dict]) -> dict:
    return {
        "source": "upcoming",
        "note": note,
        "min_projection": MIN_PROJECTION,
        "featured": 0,
        "trained_through": trained,
        "updated": _clock(),
        "today": current.isoformat(),
        "refresh_seconds": 20,
        "weeks": weeks,
    }


def _trained_through(logs: list[GameLog]) -> str:
    if not logs:
        return "no completed games"
    last = max(logs, key=lambda log: (log.season, log.week))
    return f"{last.season} week {last.week}"


def _day_for(row, shells: list[GameLog]) -> str:
    for shell in shells:
        if shell.player_id == row.player_id and shell.season == row.season and shell.week == row.week:
            if shell.gameday:
                return shell.gameday
    return f"{row.season}-W{row.week}"


def _matchup(kick: Kickoff) -> str:
    return f"{kick.away} at {kick.home}"


def _label(day: str, today: date, matchups: list[str]) -> str:
    played_on = date.fromisoformat(day)
    if played_on == today:
        when = "Tonight"
    else:
        when = f"{played_on.strftime('%a')} {played_on.strftime('%b')} {played_on.day}"
    games = ", ".join(matchups[:4])
    if len(matchups) > 4:
        games = f"{len(matchups)} games"
    return f"{when} · {games}"


def _kickoff_label(kicks: list[Kickoff]) -> str:
    times = sorted({kick.gametime for kick in kicks if kick.gametime})
    if not times:
        return ""
    if len(times) == 1:
        return _format_time(times[0])
    return _format_time(times[0]) + "–" + _format_time(times[-1])


def _clock() -> str:
    now = datetime.now(EASTERN)
    hour = int(now.strftime("%I"))
    return f"{hour}:{now.strftime('%M:%S %p')} ET"


def _format_time(gametime: str) -> str:
    if not gametime or ":" not in gametime:
        return gametime
    hour_text, minute = gametime.split(":", 1)
    hour = int(hour_text)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute} {suffix} ET"


def _blank_score(value: object) -> bool:
    text = "" if value is None else str(value).strip().lower()
    return text in ("", "na", "nan", "null", "none")
