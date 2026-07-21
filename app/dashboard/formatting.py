from __future__ import annotations

import pandas as pd

DIRECTION_BUCKETS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def direction_bucket(degrees: float | None) -> str:
    if degrees is None or pd.isna(degrees):
        return "Unknown"
    return DIRECTION_BUCKETS[int((degrees + 22.5) // 45) % len(DIRECTION_BUCKETS)]


def format_number(value: float | int | None, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.{decimals}f}"


def rating_label(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "0.00"
    return f"{value:.2f}"

