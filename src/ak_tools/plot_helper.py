"""Plotting helper module placeholder for reusable visualization utilities."""

from __future__ import annotations

from typing import Iterable


def moving_average(values: Iterable[float], window: int = 3) -> list[float]:
    """Compute a simple moving average for a sequence of numbers.

    Args:
        values: Input sequence of numeric values.
        window: Number of values per averaging window.

    Returns:
        List of averaged values.
    """
    data = list(values)
    if window <= 0:
        raise ValueError("window must be > 0")
    if len(data) < window:
        return []

    return [sum(data[i : i + window]) / window for i in range(len(data) - window + 1)]
