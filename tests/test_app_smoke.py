"""Runtime smoke test for the Streamlit app entrypoint."""

import os
import subprocess
import sys
import unittest
from pathlib import Path


class AppRuntimeSmokeTests(unittest.TestCase):
    def test_entrypoint_renders_access_screen_without_secrets(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        runner = r"""
import sys
from streamlit.testing.v1 import AppTest

app = AppTest.from_file(sys.argv[1], default_timeout=20).run(timeout=20)
if app.exception:
    raise AssertionError(
        "Streamlit entrypoint raised: "
        + "\\n".join(str(error.value) for error in app.exception)
    )
rendered_text = "\\n".join(
    [element.value for element in app.title]
    + [element.value for element in app.header]
    + [element.value for element in app.subheader]
    + [element.value for element in app.markdown]
)
assert "AGENCIA OS" in rendered_text, "App title wasn't rendered"
assert any(widget.label == "Clave" for widget in app.text_input), (
    "The license access input wasn't rendered"
)
"""
        environment = os.environ.copy()
        for name in (
            "ADMIN_PASSWORD",
            "SUPABASE_URL",
            "SUPABASE_SECRET_KEY",
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GOOGLE_OAUTH_REDIRECT_URI",
        ):
            environment[name] = ""

        result = subprocess.run(
            [sys.executable, "-c", runner, str(app_path)],
            cwd=str(app_path.parent),
            env=environment,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg="Isolated Streamlit smoke process failed.\n"
            + result.stdout[-5000:]
            + "\n"
            + result.stderr[-5000:],
        )


if __name__ == "__main__":
    unittest.main()
