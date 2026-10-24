"""Pre-kickoff form line from earlier games only."""

from __future__ import annotations

# Newest game's weight inside the exponential average.
EWMA_ALPHA = 0.4
# Games of position-mean history mixed into a short sample.
PRIOR_STRENGTH = 4.0


def form_line(prior_points: list[float], position_mean: float) -> float:
    """Shrink an exponential average of earlier games toward the position mean.

    An empty history returns the position mean. The newest game receives
    EWMA_ALPHA of the running average. The average is then blended with the
    position mean so that PRIOR_STRENGTH games of history would split the
    weight evenly.
    """
    if not prior_points:
        return position_mean
    average = prior_points[0]
    for points in prior_points[1:]:
        average = EWMA_ALPHA * points + (1.0 - EWMA_ALPHA) * average
    games = float(len(prior_points))
    weight = games / (games + PRIOR_STRENGTH)
    return weight * average + (1.0 - weight) * position_mean
