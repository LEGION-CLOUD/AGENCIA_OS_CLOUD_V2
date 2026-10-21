import json
import unittest
from datetime import date
from unittest.mock import Mock

import requests

from meta_ads import META_API_VERSION, MetaAdsError, fetch_meta_insights, meta_date_range


class MetaDateRangeTests(unittest.TestCase):
    def test_relative_periods_are_inclusive_and_end_yesterday(self):
        today = date(2026, 10, 15)

        self.assertEqual(
            meta_date_range("last_7d", today=today),
            ("2026-10-08", "2026-10-14"),
        )
        self.assertEqual(
            meta_date_range("last_14d", today=today),
            ("2026-10-01", "2026-10-14"),
        )
        self.assertEqual(
            meta_date_range("last_30d", today=today),
            ("2026-09-15", "2026-10-14"),
        )

    def test_custom_period_preserves_exact_selected_dates(self):
        self.assertEqual(
            meta_date_range(
                "custom",
                custom_start=date(2024, 4, 7),
                custom_end=date(2024, 5, 10),
            ),
            ("2024-04-07", "2024-05-10"),
        )

    def test_rejects_reversed_and_missing_custom_dates(self):
        with self.assertRaisesRegex(ValueError, "posterior"):
            meta_date_range(
                "custom",
                custom_start=date(2026, 10, 16),
                custom_end=date(2026, 10, 15),
            )
        with self.assertRaisesRegex(ValueError, "Seleccioná"):
            meta_date_range("custom")


class MetaInsightsTests(unittest.TestCase):
    def setUp(self):
        self.get = Mock()

    def response(self, payload, status_code=200):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        return response

    def test_historical_campaign_results_are_mapped_and_exact_dates_sent(self):
        self.get.return_value = self.response({
            "data": [{
                "campaign_id": "meta-campaign-555",
                "campaign_name": "Campaign from mocked historical fixture",
                "spend": "125.50",
                "impressions": "3400",
                "ctr": "1.25",
                "cpc": "2.10",
                "actions": [{"action_type": "purchase", "value": "3"}],
                "action_values": [{"action_type": "purchase", "value": "500"}],
            }]
        })
        period = ("2024-04-07", "2024-05-10")

        result = fetch_meta_insights(
            "test-token-not-a-real-credential",
            "act_123456",
            period,
            get=self.get,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Canal"], "META")
        self.assertEqual(result.iloc[0]["Campaign ID"], "meta-campaign-555")
        self.assertEqual(result.iloc[0]["Spend"], 125.5)
        self.assertEqual(result.iloc[0]["Impressions"], 3400)
        self.assertEqual(result.iloc[0]["Conversions"], 3.0)
        self.assertAlmostEqual(result.iloc[0]["ROAS"], 500 / 125.5)
        args, kwargs = self.get.call_args
        self.assertEqual(
            args[0],
            f"https://graph.facebook.com/{META_API_VERSION}/act_123456/insights",
        )
        self.assertEqual(
            json.loads(kwargs["params"]["time_range"]),
            {"since": period[0], "until": period[1]},
        )
        self.assertFalse(kwargs["allow_redirects"])

    def test_successful_empty_response_returns_empty_frame_not_zero_metrics(self):
        self.get.return_value = self.response({"data": []})

        with self.assertLogs("meta_ads", level="INFO") as captured:
            result = fetch_meta_insights(
                "test-token-not-a-real-credential",
                "123456",
                ("2026-09-15", "2026-10-14"),
                get=self.get,
            )

        self.assertTrue(result.empty)
        self.assertEqual(len(result.columns), 10)
        diagnostic = "\n".join(captured.output)
        self.assertIn("account=act_123456", diagnostic)
        self.assertIn("since=2026-09-15 until=2026-10-14", diagnostic)
        self.assertIn("level=campaign http_status=200 graph_code=None rows=0", diagnostic)
        self.assertNotIn("test-token-not-a-real-credential", diagnostic)
        self.assertNotIn("Authorization", diagnostic)
        self.assertNotIn("graph.facebook.com", diagnostic)
        self.assertNotIn('"data": []', diagnostic)

    def test_meta_api_error_is_safe_and_includes_http_and_graph_code(self):
        self.get.return_value = self.response(
            {
                "error": {
                    "code": 190,
                    "message": "private-meta-error-message",
                }
            },
            status_code=400,
        )

        with self.assertLogs("meta_ads", level="WARNING") as captured:
            with self.assertRaises(MetaAdsError) as raised:
                fetch_meta_insights(
                    "test-token-not-a-real-credential",
                    "123456",
                    ("2026-09-15", "2026-10-14"),
                    get=self.get,
                )

        message = str(raised.exception)
        self.assertIn("HTTP 400", message)
        self.assertIn("código Graph 190", message)
        self.assertNotIn("test-token-not-a-real-credential", message)
        self.assertNotIn("private-meta-error-message", message)
        diagnostic = "\n".join(captured.output)
        self.assertIn("account=act_123456", diagnostic)
        self.assertIn("since=2026-09-15 until=2026-10-14", diagnostic)
        self.assertIn("level=campaign http_status=400 graph_code=190 rows=0", diagnostic)
        self.assertNotIn("test-token-not-a-real-credential", diagnostic)
        self.assertNotIn("Authorization", diagnostic)
        self.assertNotIn("graph.facebook.com", diagnostic)
        self.assertNotIn("private-meta-error-message", diagnostic)

    def test_connection_failure_does_not_expose_request_exception_text(self):
        self.get.side_effect = requests.ConnectionError(
            "request included test-token-not-a-real-credential"
        )

        with self.assertRaises(MetaAdsError) as raised:
            fetch_meta_insights(
                "test-token-not-a-real-credential",
                "123456",
                ("2026-09-15", "2026-10-14"),
                get=self.get,
            )

        self.assertNotIn("test-token-not-a-real-credential", str(raised.exception))
        self.assertIn("No se pudo conectar", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
