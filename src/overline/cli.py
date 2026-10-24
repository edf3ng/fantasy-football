"""Command line for the weekly over-line board."""

from __future__ import annotations

import argparse

from overline.board import assemble
from overline.slate import cache_path, fetch_logs, load_cache, sample_logs
from overline.web import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="overline",
        description="Rank players the model expects to score above their weekly form line.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Download nflverse stats into data/cache")
    fetch.add_argument("--refresh", action="store_true", help="Download again even if a cache exists")

    rank = sub.add_parser("rank", help="Print one week's board")
    _add_slate_flags(rank)
    rank.add_argument("--season", type=int)
    rank.add_argument("--week", type=int)

    backtest = sub.add_parser("backtest", help="Print hit rate against the base rate")
    _add_slate_flags(backtest)

    server = sub.add_parser("serve", help="Open the local board")
    _add_slate_flags(server)
    server.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)
    if args.command == "fetch":
        path = fetch_logs(refresh=args.refresh)
        logs = load_cache(path)
        seasons = sorted({log.season for log in logs})
        print(f"Cached {len(logs)} games in {path}")
        if seasons:
            print(f"Seasons {seasons[0]}–{seasons[-1]}")
        return 0

    payload = _payload(args.sample)
    if args.command == "serve":
        if not payload["weeks"]:
            print("No week had enough earlier games to fit.")
            return 1
        serve(payload, args.port)
        return 0
    if args.command == "backtest":
        return _print_backtest(payload)
    return _print_rank(payload, args.season, args.week)


def _add_slate_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sample", action="store_true", help="Use the synthetic league instead of the cache")


def _payload(sample: bool) -> dict:
    if sample:
        return assemble(
            sample_logs(),
            source="sample",
            note="Sample slate. NOR, SOU, EAS, and WES are synthetic teams, not NFL results. Home games were given extra points so the context window has a site effect to find.",
        )
    path = cache_path()
    if not path.exists():
        raise SystemExit(f"No cache at {path}. Run: PYTHONPATH=src python3 -m overline fetch")
    logs = load_cache(path)
    seasons = sorted({log.season for log in logs})
    span = f"{seasons[0]}–{seasons[-1]}" if seasons else "the downloaded seasons"
    return assemble(
        logs,
        source="nflverse",
        note=(
            f"Backtest from nflverse regular-season games, {span}. "
            "The form line is a shrunk average of earlier games, not a published consensus. "
            "Only players who recorded a stat line are listed."
        ),
    )


def _print_rank(payload: dict, season: int | None, week: int | None) -> int:
    chosen = _select(payload, season, week)
    if chosen is None:
        print("That week is not on the board. It needs 60 earlier feature rows, or it had no one over the line.")
        return 1
    print(payload["note"])
    print(f"{chosen['season']} week {chosen['week']}")
    print(f"{'Player':<22} {'Pos':<4} {'Opp':<8} {'Line':>6} {'Model':>6} {'Edge':>6} {'P':>5} {'Actual':>7}")
    for index, player in enumerate(chosen["players"], start=1):
        opp = f"@{player['opponent']}" if player["site"] == "away" else player["opponent"]
        print(
            f"{index:>2} {player['name']:<19} {player['position']:<4} {opp:<8} "
            f"{player['projection']:6.1f} {player['expected']:6.1f} {player['edge']:+6.1f} "
            f"{player['p_beat']*100:4.0f}% {player['actual']:7.1f}"
        )
    return 0


def _print_backtest(payload: dict) -> int:
    print(payload["note"])
    print(f"{'Week':<14} {'Board':>7} {'Hit':>7} {'Base':>7}")
    board_hits = board_n = base_hits = base_n = 0
    for week in payload["weeks"]:
        board_hits += week["hits"]
        board_n += len(week["players"])
        base_hits += week["eligible_hits"]
        base_n += week["eligible"]
        print(
            f"{week['season']} w{week['week']:<8} {len(week['players']):7d} "
            f"{_percent(week['hits'], len(week['players'])):>7} "
            f"{_percent(week['eligible_hits'], week['eligible']):>7}"
        )
    print(
        f"{'All weeks':<14} {board_n:7d} {_percent(board_hits, board_n):>7} {_percent(base_hits, base_n):>7}"
    )
    return 0


def _select(payload: dict, season: int | None, week: int | None) -> dict | None:
    weeks = payload["weeks"]
    if not weeks:
        return None
    if season is None and week is None:
        return weeks[payload.get("featured", len(weeks) - 1)]
    for item in weeks:
        if season is not None and item["season"] != season:
            continue
        if week is not None and item["week"] != week:
            continue
        return item
    return None


def _percent(hits: int, trials: int) -> str:
    if not trials:
        return "—"
    return f"{100.0 * hits / trials:.0f}%"
