import json
import unittest
from io import BytesIO
from unittest.mock import Mock

import pandas as pd
import requests

from app import invalidate_license_session, start_license_session
from tiktok_ads import (
    TIKTOK_REPORT_COLUMNS,
    TikTokAdsError,
    TikTokReportConfig,
    export_report_csv,
    export_report_excel,
    fetch_campaign_report,
    normalize_advertiser_id,
)


class TikTokReportTests(unittest.TestCase):
    def setUp(self):
        self.token = "test-token-not-a-real-credential"
        self.get = Mock()

    def response(self, rows, total_pages=1, status_code=200, code=0):
        response = Mock(status_code=status_code)
        response.json.return_value = {
            "code": code,
            "data": {
                "list": rows,
                "page_info": {"total_page": total_pages},
            },
        }
        return response

    def row(self, campaign, spend, impressions, clicks="0", report_date="2026-10-14"):
        return {
            "dimensions": {
                "campaign_id": "123",
                "stat_time_day": report_date,
            },
            "metrics": {
                "campaign_name": campaign,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
            },
        }

    def test_report_uses_official_v13_get_contract_and_selected_period(self):
        self.get.return_value = self.response([
            self.row("Campaign fixture", "125.50", "3400")
        ])

        report = fetch_campaign_report(
            self.token,
            " 123456789 ",
            ("2026-10-01", "2026-10-14"),
            get=self.get,
        )

        self.assertEqual(len(report), 1)
        self.assertEqual(report.iloc[0]["Canal"], "TIKTOK")
        self.assertEqual(report.iloc[0]["Campaign ID"], "123")
        self.assertEqual(report.iloc[0]["Campaign"], "Campaign fixture")
        self.assertEqual(report.iloc[0]["Spend"], 125.5)
        self.assertEqual(report.iloc[0]["Impressions"], 3400)
        self.assertEqual(report.iloc[0]["Clicks"], 0)
        self.assertEqual(report.iloc[0]["CTR"], 0)
        self.assertIsNone(report.iloc[0]["CPC"])
        self.assertIsNone(report.iloc[0]["Revenue"])
        args, kwargs = self.get.call_args
        self.assertEqual(args[0], "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/")
        self.assertEqual(kwargs["headers"]["Access-Token"], self.token)
        params = kwargs["params"]
        self.assertEqual(params["advertiser_id"], "123456789")
        self.assertEqual(params["report_type"], "BASIC")
        self.assertEqual(params["data_level"], "AUCTION_CAMPAIGN")
        self.assertEqual(json.loads(params["dimensions"]), ["campaign_id", "stat_time_day"])
        self.assertEqual(json.loads(params["metrics"]), ["campaign_name", "spend", "impressions", "clicks"])
        self.assertEqual(params["start_date"], "2026-10-01")
        self.assertEqual(params["end_date"], "2026-10-14")
        self.assertEqual(params["page_size"], 1000)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertNotIn("json", kwargs)
        self.assertNotIn(self.token, str(params))

    def test_report_calculates_click_metrics_and_handles_zero_denominators(self):
        self.get.return_value = self.response([
            self.row("Measured campaign", "125.50", "3400", clicks="68"),
            self.row("No impressions", "12.00", "0", clicks="0"),
            self.row("No clicks", "12.00", "100", clicks="0"),
            self.row("Low impression suppression", "2.00", "<5", clicks="1"),
        ])

        report = fetch_campaign_report(
            self.token,
            "123456789",
            ("2026-10-01", "2026-10-14"),
            get=self.get,
        )

        first = report.iloc[0]
        self.assertAlmostEqual(first["CTR"], 2.0)
        self.assertAlmostEqual(first["CPC"], 125.50 / 68)
        no_impressions = report.iloc[1]
        self.assertTrue(pd.isna(no_impressions["CTR"]))
        self.assertTrue(pd.isna(no_impressions["CPC"]))
        no_clicks = report.iloc[2]
        self.assertEqual(no_clicks["CTR"], 0)
        self.assertTrue(pd.isna(no_clicks["CPC"]))
        suppressed = report.iloc[3]
        self.assertTrue(pd.isna(suppressed["Impressions"]))
        self.assertTrue(pd.isna(suppressed["CTR"]))

    def test_pagination_fetches_each_page_once(self):
        self.get.side_effect = [
            self.response([self.row("Page one", "10", "100")], total_pages=2),
            self.response([self.row("Page two", "20", "200")], total_pages=2),
        ]

        report = fetch_campaign_report(
            self.token,
            "123456789",
            ("2026-10-01", "2026-10-14"),
            get=self.get,
        )

        self.assertEqual(report["Campaign"].tolist(), ["Page one", "Page two"])
        self.assertEqual(self.get.call_count, 2)
        self.assertEqual(self.get.call_args_list[0].kwargs["params"]["page"], 1)
        self.assertEqual(self.get.call_args_list[1].kwargs["params"]["page"], 2)

    def test_empty_success_returns_empty_report_with_stable_columns(self):
        self.get.return_value = self.response([], total_pages=0)

        report = fetch_campaign_report(
            self.token,
            "123456789",
            ("2026-10-01", "2026-10-14"),
            get=self.get,
        )

        self.assertTrue(report.empty)
        self.assertEqual(report.columns.tolist(), TIKTOK_REPORT_COLUMNS)
        self.assertEqual(self.get.call_count, 1)

    def test_invalid_credentials_advertiser_and_dates_fail_before_request(self):
        with self.assertRaisesRegex(TikTokAdsError, "token"):
            fetch_campaign_report(
                " ", "123456789", ("2026-10-01", "2026-10-14"), get=self.get
            )
        with self.assertRaisesRegex(ValueError, "solo dígitos"):
            normalize_advertiser_id("123abc")
        with self.assertRaisesRegex(ValueError, "posterior"):
            fetch_campaign_report(
                self.token,
                "123456789",
                ("2026-10-15", "2026-10-14"),
                get=self.get,
            )
        with self.assertRaisesRegex(ValueError, "máximo de 30 días"):
            fetch_campaign_report(
                self.token,
                "123456789",
                ("2026-09-01", "2026-10-01"),
                get=self.get,
            )
        self.get.assert_not_called()

    def test_thirty_day_inclusive_range_is_accepted(self):
        self.get.return_value = self.response([], total_pages=0)

        fetch_campaign_report(
            self.token,
            "123456789",
            ("2026-09-15", "2026-10-14"),
            get=self.get,
        )

        params = self.get.call_args.kwargs["params"]
        self.assertEqual(params["start_date"], "2026-09-15")
        self.assertEqual(params["end_date"], "2026-10-14")

    def test_api_and_transport_errors_never_expose_token_or_response_body(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "code": 40002,
            "message": f"private body {self.token}",
        }
        self.get.return_value = response

        with self.assertRaises(TikTokAdsError) as raised:
            fetch_campaign_report(
                self.token,
                "123456789",
                ("2026-10-01", "2026-10-14"),
                get=self.get,
            )
        self.assertNotIn(self.token, str(raised.exception))
        self.assertNotIn("private body", str(raised.exception))

        self.get.side_effect = requests.ConnectionError(
            f"request failed with {self.token}"
        )
        with self.assertRaises(TikTokAdsError) as raised:
            fetch_campaign_report(
                self.token,
                "123456789",
                ("2026-10-01", "2026-10-14"),
                get=self.get,
            )
        self.assertNotIn(self.token, str(raised.exception))

    def test_report_errors_are_safe_for_http_and_malformed_responses(self):
        self.get.return_value = self.response([], status_code=403)
        with self.assertRaisesRegex(TikTokAdsError, "HTTP 403"):
            fetch_campaign_report(
                self.token,
                "123456789",
                ("2026-10-01", "2026-10-14"),
                get=self.get,
            )

        malformed = Mock(status_code=200)
        malformed.json.return_value = {"code": 0, "data": {"list": []}}
        self.get.return_value = malformed
        with self.assertRaisesRegex(TikTokAdsError, "formato no válido"):
            fetch_campaign_report(
                self.token,
                "123456789",
                ("2026-10-01", "2026-10-14"),
                get=self.get,
            )

    def test_exporters_create_csv_and_excel_for_data_and_empty_reports(self):
        report = pd.DataFrame(
            [{"Canal": "TIKTOK", "Campaign": "Fixture", "Spend": 12.5}]
        )
        csv_data = export_report_csv(report)
        self.assertTrue(csv_data.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"Fixture", csv_data)

        excel_data = export_report_excel(report)
        excel_report = pd.read_excel(BytesIO(excel_data))
        self.assertEqual(excel_report.iloc[0]["Campaign"], "Fixture")
        self.assertEqual(excel_report.iloc[0]["Spend"], 12.5)

        empty_report = pd.DataFrame(columns=TIKTOK_REPORT_COLUMNS)
        self.assertIn(b"Campaign", export_report_csv(empty_report))
        self.assertFalse(pd.read_excel(BytesIO(export_report_excel(empty_report))).shape[0])

    def test_csv_export_neutralizes_formula_like_campaign_names(self):
        report = pd.DataFrame([{
            "Canal": "TIKTOK",
            "Campaign": '=HYPERLINK("https://example.invalid", "click")',
            "Spend": 12.5,
        }])

        parsed = pd.read_csv(BytesIO(export_report_csv(report)))

        self.assertEqual(
            parsed.iloc[0]["Campaign"],
            '\'=HYPERLINK("https://example.invalid", "click")',
        )
        self.assertEqual(parsed.iloc[0]["Spend"], 12.5)

    def test_config_repr_does_not_include_access_token(self):
        self.assertNotIn(
            self.token,
            repr(TikTokReportConfig(access_token=self.token)),
        )

    def test_license_change_starts_fresh_scope_and_clears_old_data(self):
        scoped_keys = (
            "meta",
            "meta_act",
            "df_meta",
            "meta_query",
            "google_oauth_credentials",
            "google_license_fingerprint",
            "df_google",
            "google_report",
            "tiktok_access_token",
            "tiktok_advertiser_id",
            "df_tiktok",
            "tiktok_report",
            "df_all",
            "gasto_all",
            "roas_all",
        )
        state = {key: "previous-license-data" for key in scoped_keys}
        state["license_valid"] = True
        state["license_data"] = {"client": "Current client"}

        start_license_session(state)
        first_scope = state["_license_scope"]
        state["df_all"] = "previous-session-aggregate"
        invalidate_license_session(state)

        self.assertTrue(all(key not in state for key in scoped_keys))
        self.assertNotIn("_license_scope", state)
        self.assertFalse(state["license_valid"])
        self.assertNotIn("license_data", state)

        state["license_data"] = {"client": "Next client"}
        start_license_session(state)
        self.assertNotEqual(first_scope, state["_license_scope"])
        self.assertFalse(state["license_valid"])
        self.assertEqual(state["license_data"], {"client": "Next client"})


if __name__ == "__main__":
    unittest.main()
