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
