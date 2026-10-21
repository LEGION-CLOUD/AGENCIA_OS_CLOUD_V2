"""Static integration guards for the current Streamlit TikTok Ads dashboard.

The full app is not executed here: AppTest currently raises a Streamlit layout-context
error in the unrelated sidebar before reaching the TikTok controls. These tests
inspect the real app source and complement the mocked API tests in test_tiktok_ads.py.
"""

import ast
from pathlib import Path
import unittest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class TikTokDashboardWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source, filename=str(APP_PATH))

    def test_current_token_advertiser_inputs_and_download_button_are_wired(self):
        self.assertIn('key="tiktok_access_token"', self.source)
        self.assertIn('key="tiktok_advertiser_id"', self.source)
        self.assertIn('st.button("Bajar TIKTOK"', self.source)
        self.assertIn('type="password"', self.source)

    def test_report_uses_normalized_advertiser_and_selected_period(self):
        normalize_at = self.source.index(
            "normalized_tiktok_advertiser = normalize_advertiser_id("
        )
        fetch_at = self.source.index("df_tiktok = fetch_campaign_report(")
        self.assertLess(
            normalize_at,
            fetch_at,
            "The advertiser ID must be validated before making the API request.",
        )
        report_call = self.source[fetch_at : self.source.index("\n    except", fetch_at)]
        self.assertIn("tiktok_access_token", report_call)
        self.assertIn("normalized_tiktok_advertiser", report_call)
        self.assertIn("selected_tiktok_period", report_call)

    def test_api_and_validation_errors_are_handled_without_fabricated_results(self):
        self.assertIn("except (TikTokAdsError, ValueError) as exc:", self.source)
        self.assertIn('"status": "error"', self.source)
        self.assertIn('"status": "empty" if df_tiktok.empty else "data"', self.source)
        self.assertIn(
            "TikTok Ads respondió correctamente sin campañas en el período consultado.",
            self.source,
        )
        self.assertIn(
            "Conversiones, valor de conversión y ROAS no se solicitan en este informe",
            self.source,
        )

    def test_csv_and_excel_exports_are_wired_for_tiktok_results(self):
        self.assertIn('key="download_tiktok_csv"', self.source)
        self.assertIn('key="download_tiktok_excel"', self.source)
        self.assertIn("data=export_report_csv(df_tiktok)", self.source)
        self.assertIn("data=export_report_excel(df_tiktok)", self.source)

    def test_dashboard_source_parses_as_valid_python(self):
        self.assertIsInstance(self.tree, ast.Module)


if __name__ == "__main__":
    unittest.main()
