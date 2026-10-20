import re
import unittest
from unittest.mock import patch

import license_security


class LicenseSecurityTests(unittest.TestCase):
    def test_fingerprint_uses_sha256_and_normalizes_key(self):
        expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
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
        self.assertEqual(key, f"LEGION-2026-{'A' * 48}")


if __name__ == "__main__":
    unittest.main()
