import unittest
from io import BytesIO

import pandas as pd

from safe_csv import dataframe_to_csv_bytes, escape_csv_cell, escape_csv_record


class SafeCsvTests(unittest.TestCase):
    def test_formula_prefixes_are_neutralized(self):
        for value in (
            "=1+1",
            "+SUM(A1:A2)",
            "-1+2",
            "@SUM(A1:A2)",
            "   =HYPERLINK(\"https://example.invalid\",\"click\")",
            "\t=1+1",
            "\r\n+1+1",
        ):
            with self.subTest(value=value):
                self.assertEqual(escape_csv_cell(value), "'" + value)

    def test_plain_text_and_non_string_values_are_preserved(self):
        self.assertEqual(escape_csv_cell("Campaign name"), "Campaign name")
        self.assertEqual(escape_csv_cell("  notes"), "  notes")
        self.assertEqual(escape_csv_cell(12.5), 12.5)
        self.assertIsNone(escape_csv_cell(None))

    def test_record_export_returns_a_new_mapping_and_preserves_numeric_fields(self):
        original = {"Campaign": "=cmd|'/C calc'!A0", "Spend": 25.5}
        escaped = escape_csv_record(original)
        self.assertEqual(escaped["Campaign"], "'=cmd|'/C calc'!A0")
        self.assertEqual(escaped["Spend"], 25.5)
        self.assertEqual(original["Campaign"], "=cmd|'/C calc'!A0")

    def test_dataframe_csv_escapes_untrusted_text_and_keeps_numeric_data(self):
        frame = pd.DataFrame([
            {"Campaign": "=HYPERLINK(\"https://example.invalid\",\"click\")", "Spend": 5.0},
            {"Campaign": "Normal campaign", "Spend": 6.0},
        ])
        payload = dataframe_to_csv_bytes(frame)

        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
        restored = pd.read_csv(BytesIO(payload))
        self.assertEqual(
            restored.iloc[0]["Campaign"],
            "'=HYPERLINK(\"https://example.invalid\",\"click\")",
        )
        self.assertEqual(restored.iloc[0]["Spend"], 5.0)
        self.assertEqual(restored.iloc[1]["Campaign"], "Normal campaign")


if __name__ == "__main__":
    unittest.main()
