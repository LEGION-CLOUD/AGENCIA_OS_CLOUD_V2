import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock

import requests

from google_ads import (
    GOOGLE_ADS_SCOPE,
    GoogleAdsError,
    GoogleOAuthConfig,
    build_authorization_url,
    build_campaign_query,
    capture_oauth_callback,
    complete_oauth_callback,
    create_oauth_state,
    exchange_authorization_code,
    fetch_google_campaigns,
    fingerprint_license,
    get_valid_access_token,
    load_oauth_config,
    normalize_customer_id,
    validate_oauth_state,
)


class GoogleOAuthTests(unittest.TestCase):
    def setUp(self):
        self.config = GoogleOAuthConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://example.test/oauth/callback",
        )

    def test_configuration_requires_https_redirect_and_names_missing_settings(self):
        with self.assertRaisesRegex(GoogleAdsError, "GOOGLE_OAUTH_CLIENT_ID"):
            load_oauth_config({})
        with self.assertRaisesRegex(GoogleAdsError, "HTTPS"):
            load_oauth_config({
                "GOOGLE_OAUTH_CLIENT_ID": "id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
                "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8501",
            })

    def test_authorization_url_requests_offline_ads_scope_and_state(self):
        license_key = "LEGION-9RLI-2026-NICO"
        license_fp = fingerprint_license(license_key, self.config)
        state = create_oauth_state(self.config, license_fp, now=1000)
        url = build_authorization_url(self.config, state)
        query = parse_qs(urlparse(url).query)

        self.assertEqual(urlparse(url).scheme, "https")
        self.assertEqual(query["scope"], [GOOGLE_ADS_SCOPE])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["state"], [state])
        self.assertNotIn(license_key, state)
        self.assertNotIn("session-access-token", state)
        self.assertNotIn("authorization-code", state)
        self.assertNotIn(self.config.client_secret, url)

    def test_signed_state_is_valid_in_a_new_session_and_license_fingerprint_matches(self):
        license_key = "LEGION-9RLI-2026-NICO"
        license_fp = fingerprint_license(license_key, self.config)
        equivalent_fp = fingerprint_license(
            "  legion-9rli-2026-nico ",
            self.config,
        )
        state = create_oauth_state(self.config, license_fp, now=1000)
        initiating_session = {"google_oauth_state": state}
        callback_session = {}
        self.assertTrue(
            capture_oauth_callback(
                {"code": "authorization-code", "state": state},
                callback_session,
            )
        )
        post = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "session-access-token",
            "refresh_token": "session-refresh-token",
            "expires_in": 3600,
        }
        post.return_value = response

        pending = callback_session.pop("google_oauth_pending_callback")
        credentials = complete_oauth_callback(
            pending["code"],
            pending["state"],
            self.config,
            equivalent_fp,
            now=1100,
            post=post,
        )
        callback_session["google_oauth_credentials"] = credentials

        self.assertNotIn("google_oauth_credentials", initiating_session)
        self.assertEqual(
            callback_session["google_oauth_credentials"]["access_token"],
            "session-access-token",
        )
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_signed_state_rejects_tampering_expiry_malformed_and_wrong_license(self):
        license_fp = fingerprint_license("LEGION-9RLI-2026-NICO", self.config)
        state = create_oauth_state(self.config, license_fp, now=1000)

        self.assertTrue(validate_oauth_state(state, self.config, license_fp, now=1100))
        self.assertFalse(
            validate_oauth_state(
                state[:-1] + ("A" if state[-1] != "A" else "B"),
                self.config,
                license_fp,
                now=1100,
            )
        )
        self.assertFalse(
            validate_oauth_state(state, self.config, license_fp, now=1600)
        )
        self.assertFalse(
            validate_oauth_state("not-a-signed-state", self.config, license_fp, now=1100)
        )
        self.assertFalse(
            validate_oauth_state(
                f"A.{state.split('.')[1]}",
                self.config,
                license_fp,
                now=1100,
            )
        )
        self.assertFalse(
            validate_oauth_state(
                state,
                self.config,
                fingerprint_license("LEGION-OTHER-2026-NICO", self.config),
                now=1100,
            )
        )

    def test_invalid_state_or_oauth_error_never_exchanges_code(self):
        license_fp = fingerprint_license("LEGION-9RLI-2026-NICO", self.config)
        state = create_oauth_state(self.config, license_fp, now=1000)
        expired_state = create_oauth_state(self.config, license_fp, now=1000)
        tampered_state = state[:-1] + ("A" if state[-1] != "A" else "B")
        post = Mock()

        invalid_callbacks = (
            (
                "authorization-code",
                state,
                fingerprint_license("LEGION-OTHER-2026-NICO", self.config),
                1100,
            ),
            ("authorization-code", tampered_state, license_fp, 1100),
            ("authorization-code", expired_state, license_fp, 1600),
            ("authorization-code", "malformed", license_fp, 1100),
        )
        for code, callback_state, callback_license, current_time in invalid_callbacks:
            with self.subTest(state=callback_state[:12]):
                with self.assertRaises(GoogleAdsError):
                    complete_oauth_callback(
                        code,
                        callback_state,
                        self.config,
                        callback_license,
                        now=current_time,
                        post=post,
                    )
        with self.assertRaisesRegex(GoogleAdsError, "no autorizó"):
            complete_oauth_callback(
                None,
                state,
                self.config,
                license_fp,
                oauth_error="access_denied",
                now=1100,
                post=post,
            )
        post.assert_not_called()

    def test_authorization_code_exchange_returns_session_credentials(self):
        post = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "session-access-token",
            "refresh_token": "session-refresh-token",
            "expires_in": 3600,
        }
        post.return_value = response

        credentials = exchange_authorization_code(
            "one-time-code",
            self.config,
            post=post,
        )

        self.assertEqual(credentials["access_token"], "session-access-token")
        self.assertEqual(credentials["refresh_token"], "session-refresh-token")
        self.assertGreater(credentials["expires_at"], 0)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_code_exchange_keeps_tokens_out_of_errors(self):
        post = Mock()
        response = Mock(status_code=400)
        response.json.return_value = {
            "error": "invalid_grant",
            "access_token": "sensitive-access-token",
            "client_secret": self.config.client_secret,
        }
        post.return_value = response

        with self.assertRaises(GoogleAdsError) as raised:
            exchange_authorization_code("sensitive-auth-code", self.config, post=post)

        message = str(raised.exception)
        self.assertNotIn("sensitive-access-token", message)
        self.assertNotIn("sensitive-auth-code", message)
        self.assertNotIn(self.config.client_secret, message)

    def test_invalid_success_response_is_rejected_without_exposing_values(self):
        post = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "error": "invalid_grant",
            "refresh_token": "sensitive-refresh-token",
        }
        post.return_value = response

        with self.assertRaises(GoogleAdsError) as raised:
            exchange_authorization_code(
                "sensitive-auth-code",
                self.config,
                post=post,
            )

        self.assertNotIn("sensitive-refresh-token", str(raised.exception))
        self.assertNotIn("sensitive-auth-code", str(raised.exception))

    def test_expiring_access_token_is_refreshed_and_kept_in_session_mapping(self):
        credentials = {
            "access_token": "old-access-token",
            "refresh_token": "session-refresh-token",
            "expires_at": 1000,
        }
        post = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }
        post.return_value = response

        token = get_valid_access_token(
            credentials,
            self.config,
            now=1000,
            post=post,
        )

        self.assertEqual(token, "new-access-token")
        self.assertEqual(credentials["refresh_token"], "session-refresh-token")
        self.assertEqual(credentials["access_token"], "new-access-token")
        self.assertEqual(post.call_args.args[0], "https://oauth2.googleapis.com/token")


class GoogleAdsQueryTests(unittest.TestCase):
    def setUp(self):
        self.post = Mock()

    def response(self, payload, status_code=200):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        return response

    def test_query_uses_exact_selected_period(self):
        query = build_campaign_query(("2024-04-07", "2024-05-10"))

        self.assertIn("segments.date BETWEEN '2024-04-07' AND '2024-05-10'", query)
        self.assertIn("metrics.cost_micros", query)
        self.assertIn("metrics.conversions_value", query)

    def test_reversed_period_and_invalid_customer_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "posterior"):
            build_campaign_query(("2026-10-16", "2026-10-15"))
        with self.assertRaisesRegex(ValueError, "10 dígitos"):
            normalize_customer_id("123")

    def test_customer_id_normalization(self):
        self.assertEqual(normalize_customer_id("123-456-7890"), "1234567890")

    def test_realistic_rows_are_normalized_and_pagination_is_followed(self):
        self.post.side_effect = [
            self.response({
                "results": [{
                    "campaign": {"id": "456789", "name": "Search campaign", "status": "ENABLED"},
                    "segments": {"date": "2024-04-07"},
                    "metrics": {
                        "costMicros": "2500000",
                        "impressions": "2000",
                        "clicks": "25",
                        "ctr": 0.0125,
                        "averageCpc": "100000",
                        "conversions": 3,
                        "conversionsValue": 50,
                    },
                }],
                "nextPageToken": "next-page-token",
            }),
            self.response({"results": []}),
        ]

        result = fetch_google_campaigns(
            "test-access-token",
            "123-456-7890",
            ("2024-04-07", "2024-05-10"),
            post=self.post,
        )

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["Canal"], "GOOGLE")
        self.assertEqual(row["Campaign ID"], "456789")
        self.assertEqual(row["Spend"], 2.5)
        self.assertEqual(row["Impressions"], 2000)
        self.assertEqual(row["Clicks"], 25)
        self.assertEqual(row["CTR"], 1.25)
        self.assertEqual(row["CPC"], 0.1)
        self.assertEqual(row["Conversions"], 3)
        self.assertEqual(row["Revenue"], 50)
        self.assertEqual(row["ROAS"], 20)
        first_args, first_kwargs = self.post.call_args_list[0]
        self.assertEqual(
            first_args[0],
            "https://googleads.googleapis.com/v26/customers/1234567890/googleAds:search",
        )
        self.assertFalse(first_kwargs["allow_redirects"])
        self.assertIn(
            "segments.date BETWEEN '2024-04-07' AND '2024-05-10'",
            first_kwargs["json"]["query"],
        )
        self.assertNotIn("test-access-token", repr(first_kwargs["json"]))
        second_body = self.post.call_args_list[1].kwargs["json"]
        self.assertEqual(second_body["pageToken"], "next-page-token")

    def test_empty_response_returns_an_empty_frame(self):
        self.post.return_value = self.response({"results": []})

        result = fetch_google_campaigns(
            "test-access-token",
            "1234567890",
            ("2026-09-15", "2026-10-14"),
            post=self.post,
        )

        self.assertTrue(result.empty)
        self.assertIn("Spend", result.columns)

    def test_api_error_does_not_expose_response_or_bearer_token(self):
        self.post.return_value = self.response(
            {"error": {"message": "private API detail"}},
            status_code=403,
        )

        with self.assertRaises(GoogleAdsError) as raised:
            fetch_google_campaigns(
                "sensitive-access-token",
                "1234567890",
                ("2026-09-15", "2026-10-14"),
                post=self.post,
            )

        message = str(raised.exception)
        self.assertIn("HTTP 403", message)
        self.assertNotIn("sensitive-access-token", message)
        self.assertNotIn("private API detail", message)

    def test_connection_error_does_not_expose_request_details(self):
        self.post.side_effect = requests.ConnectionError(
            "request contained sensitive-access-token"
        )

        with self.assertRaises(GoogleAdsError) as raised:
            fetch_google_campaigns(
                "sensitive-access-token",
                "1234567890",
                ("2026-09-15", "2026-10-14"),
                post=self.post,
            )

        self.assertNotIn("sensitive-access-token", str(raised.exception))
        self.assertTrue(
            self.post.call_args.kwargs["headers"]["Authorization"].startswith("Bearer ")
        )


if __name__ == "__main__":
    unittest.main()
