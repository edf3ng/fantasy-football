# Overline

Rank the players a model expects to score **above their own weekly line**, not the players with the highest projection.

## Who makes the board

A player is eligible when both of these are true:

- The form line is at least 6 PPR points.
- The model’s expected points are higher than that line.

Eligible players are scored by:

`P(actual > line) × (expected points − line)`

The board keeps the top 25. Under the model, everyone on it is more likely than not to clear the line, because a positive surplus is what puts `P(above)` over one half.

Expected points are the form line plus a surplus (or deficit) read from that player’s context window. Rank is not “highest projection.” A 9-point player the model expects to score 14 outranks a 22-point player the model expects to score 21.

## The form line

There is no licensed expert feed in this project. The line is computed before the game from that player’s earlier PPR games only:

- Exponentially weight earlier games, newest first (weight 0.4 on the newest game).
- Shrink that average toward the position mean from earlier games. Four games of history is the prior strength, so a single spike barely moves the line.
- With no earlier game, the player is left off the board. There is no line to beat.

Tight ends are the reference position when the model compares positions. The line itself is not a feature inside the surplus regression. If it were, shrinkage toward the league mean would stuff the board with low lines and fade stars. The model is only allowed to move a player off the line.

## The context window

These nine fields are the model’s entire input for the surplus. Each one is knowable before kickoff. Current-week yards, scores, targets, and carries are labels, not inputs.

| Slot | Field | Definition |
| --- | --- | --- |
| 1 | Recent trend | Mean of up to the last three games, minus the season average |
| 2 | Games this season | Earlier games this season |
| 3 | Targets, last three | Mean targets over those prior games |
| 4 | Carries, last three | Mean carries over those prior games |
| 5 | Home | 1 when the schedule lists the team as home and the site is not neutral |
| 6 | Opponent allowed | Mean PPR the opponent allowed to this position over up to eight earlier weeks |
| 7 | Quarterback | 1 if QB, else 0 |
| 8 | Running back | 1 if RB, else 0 |
| 9 | Wide receiver | 1 if WR, else 0 |

The form line is shown beside the window so the arithmetic is visible: line + surplus = expected points. The window also shows each field’s raw value, the value after training-set standardization, the ridge weight, and the points that slot pulls onto the surplus. Those pulls plus the intercept equal the surplus.

## The model

Walk forward one week at a time. Fit on feature rows from earlier weeks only, then score the target week.

- Standardize each context field with the training mean and standard deviation.
- Ridge regression (penalty 5 on every weight except the intercept) predicts the surplus, `actual − line`.
- Residual scale is the root mean squared error of that fit, computed separately by position when a position has at least 30 training residuals, otherwise the global scale. The scale is at least 1.5 PPR.
- `P(actual > line)` treats the residual as normal: `Φ(surplus / position scale)`.

The first season needs 60 prior feature rows before a week is scored. Until then the week is omitted rather than shown with an unfitted model.

## Leakage rules

For a player in week `t`:

- The line, trend, usage, and season counts use games before `t` only.
- Opponent points allowed use that defense’s earlier weeks only, not week `t`.
- Home or neutral comes from the schedule, not from the result.
- Training rows for week `t` stop at week `t − 1`.
- Changing week `t` or any later week’s box score must not change week `t`’s context window.

## Data

Public nflverse weekly player stats and schedules. `fetch` keeps regular-season QB, RB, WR, and TE games from 2023 forward in `data/cache/logs.csv` (gitignored). Points are nflverse PPR, which is the standard 1 point per reception scoring.

A built-in sample league (four teams, synthetic names, two short seasons) runs with no download. Sample results are labeled synthetic and are not NFL records.

## What the board is

Each listed week is a historical backtest of players who recorded a stat line. Features stop the week before. Actual points are shown so the hit rate can be compared with the base rate among everyone whose line was at least 6 PPR.

The board does not predict inactives, trades that have not hit the stat file, or weather. A row exists because the player logged a game.

## Layout

- `scoring.py` — PPR from counting stats, used when a file has no PPR column.
- `projections.py` — the shrunk form line.
- `features.py` — context windows with no future box score.
- `model.py` — ridge surplus, position error scale, chance of clearing the line.
- `rank.py` — positive surplus, minimum line, top 25 by rank score.
- `slate.py` — sample league and nflverse load.
- `board.py` — walk-forward weeks.
- `web.py` — the board and the context window.
- `cli.py` — `fetch`, `rank`, `backtest`, and `serve`.

## Out of scope

Lineup optimization, auction values, ownership, injury news, best-ball advance rates, and any paid projection product.
