import re
import unittest
from unittest.mock import patch

import license_security


class LicenseSecurityTests(unittest.TestCase):
    def test_resolve_active_license_by_fingerprint_without_exposing_key(self):
        from datetime import datetime

        key = "LEGION-TEST-ACTIVE"
        record = {
            "client": "Cliente",
            "created": "2026-10-01T00:00:00",
            "expires": "2026-12-31T00:00:00",
            "max_accounts": 3,
            "active": True,
        }
        resolved = license_security.resolve_active_license_for_fingerprint(
            {key: record},
            license_security.license_key_fingerprint(key),
            now=datetime(2026, 10, 21, 12, 0, 0),
        )
        self.assertEqual(resolved, record)
        self.assertIsNot(resolved, record)

    def test_resolve_active_license_rejects_inactive_expired_missing_and_invalid(self):
        from datetime import datetime

        now = datetime(2026, 10, 21, 12, 0, 0)
        active_key = "LEGION-ACTIVE"
        inactive_key = "LEGION-INACTIVE"
        expired_key = "LEGION-EXPIRED"
        licenses = {
            active_key: {"active": True, "expires": "2026-12-31T00:00:00"},
            inactive_key: {"active": False, "expires": "2026-12-31T00:00:00"},
            expired_key: {"active": True, "expires": "2026-10-20T00:00:00"},
        }

        self.assertIsNotNone(license_security.resolve_active_license_for_fingerprint(
            licenses, license_security.license_key_fingerprint(active_key), now=now
        ))
        self.assertIsNone(license_security.resolve_active_license_for_fingerprint(
            licenses, license_security.license_key_fingerprint(inactive_key), now=now
        ))
        self.assertIsNone(license_security.resolve_active_license_for_fingerprint(
            licenses, license_security.license_key_fingerprint(expired_key), now=now
        ))
        self.assertIsNone(license_security.resolve_active_license_for_fingerprint(
            licenses, license_security.license_key_fingerprint("MISSING"), now=now
        ))
        self.assertIsNone(license_security.resolve_active_license_for_fingerprint(
            licenses, "not-a-fingerprint", now=now
        ))

    def test_resolve_active_license_rejects_malformed_expiration(self):
        from datetime import datetime

        key = "LEGION-BAD-EXPIRATION"
        result = license_security.resolve_active_license_for_fingerprint(
            {key: {"active": True, "expires": "not a date"}},
            license_security.license_key_fingerprint(key),
            now=datetime(2026, 10, 21),
        )
        self.assertIsNone(result)

    def test_fingerprint_uses_sha256_and_normalizes_key(self):
        expected = "b5d4045c3f466fa91fe2cc6abe79232a1a57cdf104f7a26e716e0a1e2789df78"
        self.assertEqual(license_security.license_key_fingerprint(" abc "), expected)
        self.assertEqual(
            license_security.license_key_fingerprint("ABC"),
            license_security.license_key_fingerprint(" abc "),
        )

    def test_matches_keys_against_fingerprints_not_plaintext(self):
        fixture_key = "TEST-EXPOSED-LICENSE"
        fingerprint = license_security.license_key_fingerprint(fixture_key)
        with patch.object(
            license_security,
            "EXPOSED_LICENSE_FINGERPRINTS",
            frozenset({fingerprint}),
        ):
            self.assertTrue(license_security.is_exposed_license_key(fixture_key.lower()))
            matches = license_security.find_exposed_license_keys({
                fixture_key: {"client": "fixture", "active": True},
                "UNRELATED-KEY": {"client": "other", "active": True},
            })
        self.assertEqual(list(matches), [fixture_key])

    def test_inactive_exposed_keys_are_not_scheduled_for_rotation_again(self):
        fixture_key = "TEST-EXPOSED-LICENSE"
        fingerprint = license_security.license_key_fingerprint(fixture_key)
        licenses = {
            fixture_key: {"client": "cliente", "active": False},
            "OTHER-EXPOSED-KEY": {"client": "otro", "active": True},
        }
        other_fingerprint = license_security.license_key_fingerprint("OTHER-EXPOSED-KEY")
        with patch.object(
            license_security,
            "EXPOSED_LICENSE_FINGERPRINTS",
            frozenset({fingerprint}),
        ):
            found = license_security.find_exposed_license_keys(licenses)
            updated, replacements = license_security.build_license_rotation_plan(
                licenses, key_factory=lambda: "NEW-KEY"
            )
        self.assertEqual(found, {})
        self.assertEqual(replacements, [])
        self.assertEqual(updated, licenses)

    def test_active_exposed_key_is_found_but_inactive_key_is_ignored(self):
        old_active = "TEST-EXPOSED-LICENSE-ACTIVE"
        old_inactive = "TEST-EXPOSED-LICENSE-INACTIVE"
        fingerprints = {
            license_security.license_key_fingerprint(old_active),
            license_security.license_key_fingerprint(old_inactive),
        }
        with patch.object(
            license_security,
            "EXPOSED_LICENSE_FINGERPRINTS",
            frozenset(fingerprints),
        ):
            found = license_security.find_exposed_license_keys({
                old_active: {"active": True},
                old_inactive: {"active": False},
            })
        self.assertEqual(list(found), [old_active])

    def test_known_exposure_fingerprints_are_sha256_hashes(self):
        self.assertEqual(len(license_security.EXPOSED_LICENSE_FINGERPRINTS), 2)
        self.assertTrue(
            all(re.fullmatch(r"[0-9a-f]{64}", item)
                for item in license_security.EXPOSED_LICENSE_FINGERPRINTS)
        )

    def test_generated_license_has_192_bits_of_random_material(self):
        with patch("license_security.secrets.token_hex", return_value="a" * 48) as token_hex:
            key = license_security.generate_license_key(year=2026)
        token_hex.assert_called_once_with(24)
        self.assertRegex(key, r"^LEGION-2026-[0-9A-F]{48}$")

    def test_rotation_preserves_metadata_and_disables_old_key(self):
        old_key = "TEST-EXPOSED-LICENSE"
        fingerprint = license_security.license_key_fingerprint(old_key)
        original = {
            old_key: {
                "client": "cliente",
                "created": "2026-01-01T00:00:00",
                "expires": "2026-12-31T00:00:00",
                "max_accounts": 3,
                "active": True,
            },
            "UNRELATED-KEY": {
                "client": "otro",
                "created": "2026-01-01T00:00:00",
                "expires": "2027-01-01T00:00:00",
                "max_accounts": 5,
                "active": True,
            },
        }
        with patch.object(license_security, "EXPOSED_LICENSE_FINGERPRINTS", frozenset({fingerprint})):
            updated, replacements = license_security.build_license_rotation_plan(
                original, key_factory=lambda: "NEW-SECURE-KEY"
            )
        self.assertFalse(updated[old_key]["active"])
        self.assertTrue(updated["NEW-SECURE-KEY"]["active"])
        self.assertEqual(updated["NEW-SECURE-KEY"]["client"], "cliente")
        self.assertEqual(updated["NEW-SECURE-KEY"]["expires"], original[old_key]["expires"])
        self.assertEqual(updated["NEW-SECURE-KEY"]["max_accounts"], 3)
        self.assertTrue(updated["UNRELATED-KEY"]["active"])
        self.assertEqual(replacements, [{
            "client": "cliente",
            "license_key": "NEW-SECURE-KEY",
            "expires": "2026-12-31T00:00:00",
            "max_accounts": 3,
        }])

    def test_new_license_record_validates_and_preserves_expected_metadata(self):
        from datetime import datetime, timedelta

        now = datetime(2026, 10, 21, 12, 0, 0)
        key, record = license_security.create_license_record(
            "  Lula  ",
            90,
            3,
            existing_keys={"LEGION-2026-EXISTING"},
            key_factory=lambda: "LEGION-2026-NEW",
            now=now,
        )

        self.assertEqual(key, "LEGION-2026-NEW")
        self.assertEqual(record["client"], "Lula")
        self.assertEqual(record["created"], now.isoformat())
        self.assertEqual(record["expires"], (now + timedelta(days=90)).isoformat())
        self.assertEqual(record["max_accounts"], 3)
        self.assertTrue(record["active"])

    def test_new_license_record_rejects_invalid_client_duration_and_account_limit(self):
        from datetime import datetime

        valid = {"key_factory": lambda: "NEW-KEY", "now": datetime(2026, 10, 21)}
        invalid_cases = [
            ("", 90, 3, "nombre del cliente"),
            ("Cliente", 0, 3, "duración"),
            ("Cliente", -1, 3, "duración"),
            ("Cliente", 1.5, 3, "duración"),
            ("Cliente", 36501, 3, "máximo permitido"),
            ("Cliente", 90, 0, "máximo de cuentas"),
            ("Cliente", 90, 1.5, "máximo de cuentas"),
        ]
        for client, days, accounts, message in invalid_cases:
            with self.subTest(client=client, days=days, accounts=accounts):
                with self.assertRaisesRegex(ValueError, message):
                    license_security.create_license_record(
                        client, days, accounts, **valid
                    )

    def test_new_license_record_retries_existing_key_collisions(self):
        from datetime import datetime

        candidates = iter(["EXISTING", "NEW-UNIQUE"])
        key, _ = license_security.create_license_record(
            "Cliente",
            30,
            1,
            existing_keys={"EXISTING"},
            key_factory=lambda: next(candidates),
            now=datetime(2026, 10, 21),
        )
        self.assertEqual(key, "NEW-UNIQUE")

    def test_rotation_rejects_key_collision(self):
        old_key = "TEST-EXPOSED-LICENSE"
        fingerprint = license_security.license_key_fingerprint(old_key)
        with patch.object(license_security, "EXPOSED_LICENSE_FINGERPRINTS", frozenset({fingerprint})):
            with self.assertRaises(RuntimeError):
                license_security.build_license_rotation_plan(
                    {old_key: {"client": "cliente", "active": True}},
                    key_factory=lambda: old_key,
                )


if __name__ == "__main__":
    unittest.main()
