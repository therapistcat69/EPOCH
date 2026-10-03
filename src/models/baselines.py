"""MODEL 0 - naive baselines (mandatory): every ML model must beat these to be worth anything.

All take a feature frame with `relative_position` and ignore everything else.
"""
import numpy as np


class ConstantBaseline:
    name = "naive_constant"

    def fit(self, df, y):
        self.value = float(np.mean(y))
        return self

    def predict(self, df):
        return np.full(len(df), self.value)


class MeanByPositionBaseline:
    """Average retention by relative-position bin (the strongest 'no-text' baseline)."""

    name = "naive_mean_by_position"

    def __init__(self, bins: int = 20):
        self.bins = bins

    def fit(self, df, y):
        idx = np.minimum((df["relative_position"].to_numpy() * self.bins).astype(int), self.bins - 1)
        y = np.asarray(y, float)
        self.means = np.array([y[idx == b].mean() if (idx == b).any() else np.nan for b in range(self.bins)])
        self.means = np.where(np.isnan(self.means), np.nanmean(self.means), self.means)
        return self

    def predict(self, df):
        idx = np.minimum((df["relative_position"].to_numpy() * self.bins).astype(int), self.bins - 1)
        return self.means[idx]


class LinearDecayBaseline:
    """R = 100 - a * relative_position, with a fit by least squares through (0, 100)."""

    name = "naive_linear_decay"

    def fit(self, df, y):
        x = df["relative_position"].to_numpy()
        self.a = float(((100.0 - np.asarray(y, float)) * x).sum() / max((x * x).sum(), 1e-9))
        return self

    def predict(self, df):
        return np.clip(100.0 - self.a * df["relative_position"].to_numpy(), 0, 100)


class PolynomialBaseline:
    name = "naive_polynomial_deg3"

    def __init__(self, degree: int = 3):
        self.degree = degree

    def fit(self, df, y):
        self.coef = np.polyfit(df["relative_position"].to_numpy(), np.asarray(y, float), self.degree)
        return self

    def predict(self, df):
        return np.clip(np.polyval(self.coef, df["relative_position"].to_numpy()), 0, 100)


BASELINES = [ConstantBaseline, MeanByPositionBaseline, LinearDecayBaseline, PolynomialBaseline]
