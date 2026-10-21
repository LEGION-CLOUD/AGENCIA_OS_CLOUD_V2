"""CSV export helpers that neutralize spreadsheet formula injection."""

from __future__ import annotations

import pandas as pd


_FORMULA_PREFIXES = ("=", "+", "-", "@")


def escape_csv_cell(value):
    """Prefix formula-like text with an apostrophe before CSV export.

    Non-string values stay numeric or null. Leading spaces/control characters
    are considered when looking for a formula marker, but the original text is
    preserved after adding the safety prefix.
    """
    if not isinstance(value, str):
        return value
    candidate = value.lstrip(" \t\r\n")
    if candidate and candidate[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value


def escape_csv_record(record):
    """Return a sanitized copy of a mapping for a CSV writer."""
    return {key: escape_csv_cell(value) for key, value in record.items()}


def dataframe_to_csv_bytes(frame):
    """Export a DataFrame as UTF-8-with-BOM CSV with formula-like text neutralized."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("El informe debe ser una tabla de datos.")
    safe_frame = frame.copy()
    for column in safe_frame.columns:
        safe_frame[column] = safe_frame[column].map(escape_csv_cell)
    return safe_frame.to_csv(index=False).encode("utf-8-sig")
