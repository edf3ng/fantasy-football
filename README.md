# Overline

Overline ranks the fantasy players a model expects to score **above their own weekly line**. The board is not a list of the highest projections.

The line is a shrunk average of that player's earlier PPR games. Nine pre-kickoff fields — the context window — estimate the surplus over that line. Players with a positive surplus and a line of at least 6 PPR are ranked by:

`P(actual > line) × surplus`

The [plan](PLAN.md) records the line, the window, the leakage rules, and what is left out.

## Run

Python 3.9 or newer. No third-party packages.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m overline serve --sample
```

The sample league is four synthetic teams (NOR, SOU, EAS, WES). It is not an NFL result. Home games were given extra points so the context window has a site effect to find.

For real seasons, download the public nflverse tables once, then serve the backtest:

```bash
PYTHONPATH=src python3 -m overline fetch
PYTHONPATH=src python3 -m overline backtest
PYTHONPATH=src python3 -m overline serve
```

`fetch` writes `data/cache/logs.csv` (regular-season QB, RB, WR, and TE games from 2023 on). That cache is gitignored. `rank` prints one week; it defaults to the latest week that had enough history to fit.

Open the board, pick a week, and select a player. The context window lists each input, and the bar is that slot's pull on the surplus. The pulls plus the intercept equal the surplus. Actual points are shown for grading and were not an input.

Hit rate is how often the listed players beat the form line. Base rate is that same count among everyone whose line was at least 6 PPR.

## Limits

The line is not a FantasyPros, ESPN, or Yahoo projection. A historical week only includes players who recorded a stat line, so the board does not predict who will sit. Neutral sites are not treated as home.
