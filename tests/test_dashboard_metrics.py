import unittest

import pandas as pd

from dashboard_metrics import count_unique_campaigns, reports_share_period


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

    def test_reports_must_have_same_explicit_period_before_consolidation(self):
        from dashboard_metrics import reports_share_period

        self.assertTrue(reports_share_period([
            ("2026-10-01", "2026-10-20"),
            ("2026-10-01", "2026-10-20"),
        ]))
        self.assertTrue(
            reports_share_period(
                [
                    ("2026-10-01", "2026-10-20"),
                    ("2026-10-01", "2026-10-20"),
                ],
                expected_period=("2026-10-01", "2026-10-20"),
            )
        )
        self.assertFalse(
            reports_share_period(
                [
                    ("2026-10-01", "2026-10-20"),
                    ("2026-10-01", "2026-10-20"),
                ],
                expected_period=("2026-09-21", "2026-10-20"),
            )
        )
        self.assertFalse(
            reports_share_period(
                [("2026-10-01", "2026-10-20")],
                expected_period=("2026-10-01", "2026-10-19"),
            )
        )
        self.assertFalse(reports_share_period([
            ("2026-10-01", "2026-10-20"),
            ("2026-09-21", "2026-10-20"),
        ]))
        self.assertFalse(reports_share_period([
            ("2026-10-01", "2026-10-20"),
            None,
        ]))
        self.assertFalse(reports_share_period([]))

    def test_none_and_empty_report_are_handled(self):
        self.assertIsNone(count_unique_campaigns(None))
        self.assertEqual(count_unique_campaigns(pd.DataFrame(columns=[
            "Canal", "Campaign ID", "Campaign"
        ])), 0)

    def test_instagram_paid_ads_status_mirrors_meta_query_state(self):
        from dashboard_metrics import instagram_ads_status

        self.assertEqual(
            instagram_ads_status("data"),
            ("Estado disponible vía Meta", "is-ready"),
        )
        self.assertEqual(
            instagram_ads_status("empty"),
            ("Sin datos en el informe Meta", "is-empty"),
        )
        self.assertEqual(
            instagram_ads_status("error"),
            ("Revisar consulta Meta", "is-error"),
        )
        self.assertEqual(
            instagram_ads_status("pending"),
            ("Consulta pendiente a través de Meta", "is-pending"),
        )
        self.assertEqual(
            instagram_ads_status(None),
            ("Consulta pendiente a través de Meta", "is-pending"),
        )


if __name__ == "__main__":
    unittest.main()
