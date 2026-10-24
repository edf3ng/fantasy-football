"""Ridge surplus over the form line, and the chance the surplus is positive."""

from __future__ import annotations

import math
from dataclasses import dataclass

from overline.features import CONTEXT_FEATURES, CONTEXT_LABELS, FeatureRow

RIDGE_ALPHA = 5.0
MIN_POSITION_RESIDUALS = 30
MIN_SIGMA = 1.5


@dataclass
class FittedModel:
    features: tuple[str, ...]
    means: list[float]
    stds: list[float]
    weights: list[float]
    sigma: float
    sigma_by_position: dict[str, float]


@dataclass
class Slot:
    feature: str
    label: str
    raw: float
    scaled: float
    weight: float
    pull: float


@dataclass
class Prediction:
    expected: float
    edge: float
    p_beat: float
    sigma: float
    intercept: float
    slots: list[Slot]


def fit_model(
    rows: list[FeatureRow],
    alpha: float = RIDGE_ALPHA,
    features: tuple[str, ...] = CONTEXT_FEATURES,
) -> FittedModel:
    """Fit surplus = actual − form line on standardized context fields."""
    means, stds = _moments(rows, features)
    design = [_design(row, features, means, stds) for row in rows]
    target = [row.actual - row.values["projection"] for row in rows]
    gram, rhs = _normal_equations(design, target)
    width = len(features) + 1
    for index in range(1, width):
        gram[index][index] += alpha
    try:
        weights = _solve(gram, rhs)
    except ValueError:
        weights = [_mean(target)] + [0.0] * len(features)

    residuals_by_position: dict[str, list[float]] = {}
    all_residuals: list[float] = []
    for row, predictors in zip(rows, design):
        surplus = _dot(weights, predictors)
        residual = (row.actual - row.values["projection"]) - surplus
        all_residuals.append(residual)
        residuals_by_position.setdefault(row.position, []).append(residual)
    sigma = max(_rmse(all_residuals), MIN_SIGMA)
    by_position = {}
    for position, residuals in residuals_by_position.items():
        if len(residuals) >= MIN_POSITION_RESIDUALS:
            by_position[position] = max(_rmse(residuals), MIN_SIGMA)
    return FittedModel(
        features=features,
        means=means,
        stds=stds,
        weights=weights,
        sigma=sigma,
        sigma_by_position=by_position,
    )


def predict(model: FittedModel, row: FeatureRow) -> Prediction:
    """Expected points, surplus, and P(actual > line) for one player-week."""
    predictors = _design(row, model.features, model.means, model.stds)
    edge = _dot(model.weights, predictors)
    sigma = model.sigma_by_position.get(row.position, model.sigma)
    slots = []
    for index, feature in enumerate(model.features):
        scaled = predictors[index + 1]
        weight = model.weights[index + 1]
        slots.append(
            Slot(
                feature=feature,
                label=CONTEXT_LABELS.get(feature, feature),
                raw=float(row.values[feature]),
                scaled=scaled,
                weight=weight,
                pull=scaled * weight,
            )
        )
    return Prediction(
        expected=row.values["projection"] + edge,
        edge=edge,
        p_beat=_phi(edge / sigma),
        sigma=sigma,
        intercept=model.weights[0],
        slots=slots,
    )


def _moments(rows: list[FeatureRow], features: tuple[str, ...]) -> tuple[list[float], list[float]]:
    count = float(len(rows))
    means = []
    stds = []
    for feature in features:
        total = sum(row.values[feature] for row in rows)
        mean = total / count
        variance = sum((row.values[feature] - mean) ** 2 for row in rows) / count
        std = math.sqrt(variance)
        means.append(mean)
        stds.append(std if std >= 1e-8 else 1.0)
    return means, stds


def _design(
    row: FeatureRow,
    features: tuple[str, ...],
    means: list[float],
    stds: list[float],
) -> list[float]:
    scaled = [
        (row.values[feature] - mean) / std
        for feature, mean, std in zip(features, means, stds)
    ]
    return [1.0, *scaled]


def _normal_equations(design: list[list[float]], target: list[float]) -> tuple[list[list[float]], list[float]]:
    width = len(design[0])
    gram = [[0.0] * width for _ in range(width)]
    rhs = [0.0] * width
    for predictors, outcome in zip(design, target):
        for row_index, left in enumerate(predictors):
            rhs[row_index] += left * outcome
            for column_index, right in enumerate(predictors):
                gram[row_index][column_index] += left * right
    return gram, rhs


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve matrix x = rhs by Gaussian elimination with partial pivoting."""
    width = len(rhs)
    augmented = [row[:] + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(width):
        pivot = max(range(column, width), key=lambda index: abs(augmented[index][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        for column_index in range(column, width + 1):
            augmented[column][column_index] /= scale
        for row_index in range(width):
            if row_index == column:
                continue
            factor = augmented[row_index][column]
            if factor == 0.0:
                continue
            for column_index in range(column, width + 1):
                augmented[row_index][column_index] -= factor * augmented[column][column_index]
    return [augmented[index][width] for index in range(width)]


def _dot(weights: list[float], predictors: list[float]) -> float:
    return sum(weight * value for weight, value in zip(weights, predictors))


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def _rmse(residuals: list[float]) -> float:
    if not residuals:
        return MIN_SIGMA
    return math.sqrt(sum(residual * residual for residual in residuals) / float(len(residuals)))


def _phi(z: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
