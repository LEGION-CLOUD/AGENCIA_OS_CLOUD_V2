import unittest

import pandas as pd

from dashboard_metrics import count_unique_campaigns


class UniqueCampaignCountTests(unittest.TestCase):
    def test_daily_rows_are_counted_once_per_platform_and_campaign_id(self):
        report = pd.DataFrame([
            {"Canal": "META", "Campaign ID": "m-1", "Campaign": "Seasonal", "Date": None},
            {"Canal": "GOOGLE", "Campaign ID": "g-1", "Campaign": "Search", "Date": "2026-10-18"},
            {"Canal": "GOOGLE", "Campaign ID": "g-1", "Campaign": "Search", "Date": "2026-10-19"},
            {"Canal": "GOOGLE", "Campaign ID": "g-2", "Campaign": "Search", "Date": "2026-10-19"},
            {"Canal": "TIKTOK", "Campaign ID": "t-1", "Campaign": "Video", "Date": "2026-10-18"},
            {"Canal": "TIKTOK", "Campaign ID": "t-1", "Campaign": "Video", "Date": "2026-10-19"},
            # A numeric ID in different platforms must remain distinct.
            {"Canal": "META", "Campaign ID": "123", "Campaign": "Launch", "Date": None},
            {"Canal": "GOOGLE", "Campaign ID": "123", "Campaign": "Launch", "Date": "2026-10-19"},
        ])

        self.assertEqual(count_unique_campaigns(report), 6)

    def test_missing_ids_fall_back_to_names_and_blank_rows_are_ignored(self):
        report = pd.DataFrame([
            {"Canal": "META", "Campaign ID": None, "Campaign": "Brand"},
            {"Canal": "META", "Campaign ID": "", "Campaign": "Brand"},
            {"Canal": "GOOGLE", "Campaign ID": None, "Campaign": ""},
            {"Canal": "", "Campaign ID": "123", "Campaign": "Ignored"},
        ])

        self.assertEqual(count_unique_campaigns(report), 1)

    def test_unknown_identity_does_not_report_false_zero(self):
        report = pd.DataFrame([
            {"Canal": "META", "Campaign ID": None, "Campaign": None},
        ])

        self.assertIsNone(count_unique_campaigns(report))

    def test_none_and_empty_report_are_handled(self):
        self.assertIsNone(count_unique_campaigns(None))
        self.assertEqual(count_unique_campaigns(pd.DataFrame(columns=[
            "Canal", "Campaign ID", "Campaign"
        ])), 0)


if __name__ == "__main__":
    unittest.main()
