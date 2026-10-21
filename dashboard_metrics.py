"""Dashboard metrics that stay correct across campaign-day report grains."""

import pandas as pd


def count_unique_campaigns(report):
    """Count campaigns once per platform, even when a report contains daily rows.

    Prefer stable campaign IDs. Fall back to campaign names only when a source
    does not provide an ID. Return None when rows exist but contain no usable
    campaign identity, so the UI does not display a misleading zero.
    """
    if report is None:
        return None
    if getattr(report, "empty", False):
        return 0

    required = {"Canal", "Campaign ID", "Campaign"}
    if not required.issubset(set(getattr(report, "columns", []))):
        return None

    identities = report[["Canal", "Campaign ID", "Campaign"]].copy()
    for column in ("Canal", "Campaign ID", "Campaign"):
        identities[column] = (
            identities[column].astype("string").fillna("").str.strip()
        )

    identities["CampaignKey"] = identities["Campaign ID"].where(
        identities["Campaign ID"].ne(""),
        identities["Campaign"],
    )
    valid = identities["Canal"].ne("") & identities["CampaignKey"].ne("")
    if not valid.any():
        return None

    unique_pairs = identities.loc[valid, ["Canal", "CampaignKey"]].drop_duplicates()
    return int(len(unique_pairs))



def reports_share_period(periods, expected_period=None):
    """Ensure loaded reports agree, optionally requiring the current selected range."""
    normalized = []
    for period in periods or []:
        if not isinstance(period, (tuple, list)) or len(period) != 2:
            return False
        start, end = period
        if not isinstance(start, str) or not isinstance(end, str) or not start or not end:
            return False
        normalized.append((start, end))

    if not normalized or len(set(normalized)) != 1:
        return False

    if expected_period is None:
        return True
    if not isinstance(expected_period, (tuple, list)) or len(expected_period) != 2:
        return False
    expected = tuple(expected_period)
    if any(not isinstance(value, str) or not value for value in expected):
        return False
    return normalized[0] == expected


def instagram_ads_status(meta_report_status):
    """Describe Instagram's paid-ad status without claiming a separate connection.

    Instagram paid ads are queried through Meta in this app; the Meta report
    does not split rows by placement, so this status mirrors the Meta query.
    """
    statuses = {
        "data": ("Estado disponible vía Meta", "is-ready"),
        "empty": ("Sin datos en el informe Meta", "is-empty"),
        "error": ("Revisar consulta Meta", "is-error"),
    }
    return statuses.get(
        meta_report_status,
        ("Consulta pendiente a través de Meta", "is-pending"),
    )
