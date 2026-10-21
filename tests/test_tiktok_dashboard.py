"""Regression tests for the current Streamlit TikTok Ads dashboard."""

from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from tiktok_ads import TIKTOK_REPORT_COLUMNS, TikTokAdsError


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
TEST_TOKEN = "dashboard-test-token-not-a-real-credential"
TEST_ADVERTISER = "123456789"


class TikTokDashboardTests(unittest.TestCase):
    def make_dashboard(self):
        app = AppTest.from_file(str(APP_PATH))
        # Simulate an already-authenticated session without calling Supabase
        # for a real license or using a production credential.
        app.session_state["license_valid"] = True
        app.session_state["license_data"] = {"client": "Dashboard test"}
        app.session_state["_license_scope"] = "isolated-dashboard-test"
        app.session_state["_license_fingerprint"] = "test-fingerprint"
        app.session_state["_license_last_checked_at"] = datetime.now().timestamp()
        return app

    def submit_tiktok(self, report=None, error=None, advertiser=TEST_ADVERTISER):
        app = self.make_dashboard()
        mocked_fetch = patch(
            "tiktok_ads.fetch_campaign_report",
            return_value=report,
            side_effect=error,
        )
        with mocked_fetch as fetch:
            app.run()
            self.assertFalse(
                app.exception,
                msg="The dashboard should render before a TikTok query.",
            )

            app.text_input(key="tiktok_access_token").set_value(TEST_TOKEN)
            app.text_input(key="tiktok_advertiser_id").set_value(advertiser)
            app.run()

            download_button = next(
                button for button in app.button if button.label == "Bajar TIKTOK"
            )
            download_button.click()
            app.run()
            self.assertFalse(
                app.exception,
                msg="The dashboard should handle the TikTok query without crashing.",
            )

        return app, fetch

    def test_current_dashboard_calls_report_with_token_advertiser_and_period(self):
        report = pd.DataFrame(
            [
                {
                    "Canal": "TIKTOK",
                    "Campaign ID": "42",
                    "Campaign": "Campaign fixture",
                    "Status": None,
                    "Date": "2026-10-14",
                    "Spend": 12.5,
                    "Impressions": 100,
                    "Clicks": 4,
                    "CTR": 4.0,
                    "CPC": 3.125,
                    "Conversions": None,
                    "Revenue": None,
                    "ROAS": None,
                }
            ],
            columns=TIKTOK_REPORT_COLUMNS,
        )
        app, fetch = self.submit_tiktok(report=report)

        fetch.assert_called_once()
        args = fetch.call_args.args
        self.assertEqual(args[0], TEST_TOKEN)
        self.assertEqual(args[1], TEST_ADVERTISER)
        self.assertIsInstance(args[2], tuple)
        self.assertEqual(len(args[2]), 2)
        self.assertTrue(
            any("TikTok Ads devolvió 1 filas" in item.value for item in app.success)
        )
        self.assertTrue(any("Campaign fixture" in str(item.value) for item in app.dataframe))

    def test_empty_report_is_reported_as_empty_not_as_an_error(self):
        empty_report = pd.DataFrame(columns=TIKTOK_REPORT_COLUMNS)
        app, fetch = self.submit_tiktok(report=empty_report)

        fetch.assert_called_once()
        self.assertTrue(
            any(
                "sin campañas en el período consultado" in item.value
                for item in app.info
            )
        )
        self.assertFalse(
            any("No se completó la consulta de TikTok Ads" in item.value for item in app.warning)
        )

    def test_invalid_advertiser_does_not_call_tiktok_api(self):
        app, fetch = self.submit_tiktok(advertiser="123ABC")

        fetch.assert_not_called()
        self.assertTrue(
            any("solo dígitos" in item.value for item in app.warning)
        )
        self.assertNotIn(
            TEST_TOKEN,
            "\n".join(item.value for item in app.warning),
        )

    def test_safe_api_error_is_shown_without_leaking_access_token(self):
        safe_error = TikTokAdsError(
            "TikTok Ads rechazó el acceso (HTTP 403). "
            "Verificá que el token sea válido y tenga permisos de reporting."
        )
        app, fetch = self.submit_tiktok(error=safe_error)

        fetch.assert_called_once()
        warnings = "\n".join(item.value for item in app.warning)
        self.assertIn("HTTP 403", warnings)
        self.assertNotIn(TEST_TOKEN, warnings)


if __name__ == "__main__":
    unittest.main()
