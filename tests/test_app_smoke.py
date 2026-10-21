"""Runtime smoke tests for the Streamlit entrypoint."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class AppRuntimeSmokeTests(unittest.TestCase):
    def test_entrypoint_renders_the_access_screen_without_secrets(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        isolated_environment = {
            "ADMIN_PASSWORD": "",
            "SUPABASE_URL": "",
            "SUPABASE_SECRET_KEY": "",
            "GOOGLE_OAUTH_CLIENT_ID": "",
            "GOOGLE_OAUTH_CLIENT_SECRET": "",
            "GOOGLE_OAUTH_REDIRECT_URI": "",
        }

        with patch.dict(os.environ, isolated_environment, clear=False):
            app = AppTest.from_file(str(app_path), default_timeout=20).run(timeout=20)

        self.assertEqual(
            len(app.exception),
            0,
            msg="Streamlit entrypoint raised: "
            + "\n".join(str(error.value) for error in app.exception),
        )
        rendered_text = "\n".join(
            [element.value for element in app.title]
            + [element.value for element in app.header]
            + [element.value for element in app.subheader]
            + [element.value for element in app.markdown]
        )
        self.assertIn("AGENCIA OS", rendered_text)
        self.assertTrue(
            any(widget.label == "Clave" for widget in app.text_input),
            msg="The access form did not render its license input.",
        )


if __name__ == "__main__":
    unittest.main()
