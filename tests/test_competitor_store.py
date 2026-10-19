import hashlib
import json
import unittest
from datetime import date
from unittest.mock import Mock

import requests

from competitor_store import (
    CompetitorStoreError,
    create_observation,
    export_observations_json,
    load_observations,
    save_observations,
    tenant_id_for_license,
)


LICENSE = {
    "client": "Cliente de prueba",
    "created": "2026-10-19T10:20:30.123456",
    "expires": "2027-01-17T10:20:30.123456",
}
RECORD = {
    "brand": "Clima Norte (prueba ficticia)",
    "platform": "Meta",
    "observed_on": date(2026, 10, 19).isoformat(),
    "creative_format": "Imagen promocional",
    "headline": "¿Necesitás instalar un aire acondicionado?",
    "text": "Consultá por la instalación de aire acondicionado.",
    "proposition": "Instalación a domicilio.",
    "offer": "",
    "call_to_action": "Consultar por WhatsApp.",
    "destination": "WhatsApp",
    "notes": "Registro ficticio de prueba.",
}


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}", response=self
            )

    def json(self):
        return self.body


class FakeHttp:
    def __init__(self, response=None):
        self.response = response or FakeResponse([])
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.response

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.response


class CompetitorStoreTests(unittest.TestCase):
    def test_tenant_hash_is_stable_and_does_not_return_license_key(self):
        tenant_a = tenant_id_for_license(LICENSE)
        tenant_b = tenant_id_for_license(dict(LICENSE))
        self.assertEqual(tenant_a, tenant_b)
        self.assertEqual(len(tenant_a), 64)
        self.assertRegex(tenant_a, r"^[0-9a-f]{64}$")
        self.assertNotEqual(tenant_a, "LEGION-SECRET-KEY")

        expected_identity = json.dumps(
            {"client": LICENSE["client"], "created": LICENSE["created"]},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.assertEqual(
            tenant_a,
            hashlib.sha256(expected_identity.encode("utf-8")).hexdigest(),
        )

    def test_tenant_hash_requires_stable_license_fields(self):
        with self.assertRaises(ValueError):
            tenant_id_for_license({"client": "Only client"})

    def test_create_observation_normalizes_fields_and_generates_id(self):
        record = create_observation(RECORD)
        self.assertTrue(record["id"])
        self.assertEqual(record["brand"], RECORD["brand"])
        self.assertEqual(record["platform"], "Meta")
        self.assertEqual(len(record), 13)

    def test_rejects_private_source_urls(self):
        with self.assertRaises(ValueError):
            create_observation({**RECORD, "source_url": "http://127.0.0.1/admin"})

    def test_export_preserves_spanish_accents(self):
        record = create_observation(RECORD)
        content = export_observations_json([record])
        self.assertIn("Necesitás", content)
        self.assertEqual(json.loads(content)[0]["id"], record["id"])

    def test_load_filters_by_tenant_and_returns_observations(self):
        tenant = tenant_id_for_license(LICENSE)
        saved = create_observation(RECORD)
        http = FakeHttp(FakeResponse([{"tenant_id": tenant, "observations": [saved]}]))

        result = load_observations(
            "https://example.supabase.co",
            "server-only-key",
            tenant,
            http=http,
        )

        self.assertEqual(result, [saved])
        url, kwargs = http.get_calls[0]
        self.assertEqual(
            url,
            "https://example.supabase.co/rest/v1/agencia_os_competitor_observations",
        )
        self.assertEqual(kwargs["params"]["tenant_id"], f"eq.{tenant}")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer server-only-key")

    def test_load_empty_tenant_returns_empty_list(self):
        http = FakeHttp(FakeResponse([]))
        result = load_observations(
            "https://example.supabase.co",
            "server-only-key",
            tenant_id_for_license(LICENSE),
            http=http,
        )
        self.assertEqual(result, [])

    def test_save_upserts_records_and_sets_server_headers(self):
        tenant = tenant_id_for_license(LICENSE)
        http = FakeHttp(FakeResponse(None, 201))
        record = create_observation(RECORD)

        save_observations(
            "https://example.supabase.co",
            "server-only-key",
            tenant,
            [record],
            http=http,
        )

        url, kwargs = http.post_calls[0]
        self.assertIn("agencia_os_competitor_observations", url)
        self.assertEqual(kwargs["params"]["on_conflict"], "tenant_id")
        self.assertEqual(kwargs["json"]["tenant_id"], tenant)
        self.assertEqual(kwargs["json"]["observations"], [record])
        self.assertEqual(
            kwargs["headers"]["Prefer"],
            "resolution=merge-duplicates,return=minimal",
        )

    def test_save_surfaces_safe_http_error(self):
        http = FakeHttp(FakeResponse({}, 403))
        with self.assertRaises(CompetitorStoreError) as caught:
            save_observations(
                "https://example.supabase.co",
                "server-only-key",
                tenant_id_for_license(LICENSE),
                [RECORD],
                http=http,
            )
        self.assertIn("HTTP 403", str(caught.exception))
        self.assertNotIn("server-only-key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
