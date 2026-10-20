import csv
import io
import json
import unittest

from competitor_tools import (
    SOURCE_URLS,
    analyze_observation,
    compare_observations,
    create_observation,
    export_observations_csv,
    export_observations_json,
    export_variations_csv,
    export_variations_txt,
    generate_ad_variations,
    import_observations_json,
    search_observations,
    validate_source_url,
)


class CompetitorObservationTests(unittest.TestCase):
    def sample(self, **overrides):
        values = {
            "brand": "Marca ejemplo",
            "platform": "Meta",
            "source_url": "https://www.facebook.com/ads/library/?id=123",
            "observed_on": "2026-10-12",
            "creative_format": "Video",
            "headline": "¿Buscás una opción práctica?",
            "text": "Conocé el producto.",
            "proposition": "Ahorro de tiempo",
            "offer": "",
            "call_to_action": "Conocer más",
            "destination": "https://brand.example/producto",
            "notes": "",
        }
        values.update(overrides)
        return create_observation(values)

    def test_public_source_urls_are_validated_without_fetching(self):
        self.assertEqual(
            validate_source_url(" https://example.com/ad?id=1 "),
            "https://example.com/ad?id=1",
        )
        self.assertEqual(validate_source_url(""), "")
        for invalid in (
            "javascript:alert(1)",
            "file:///etc/passwd",
            "http://localhost/ad",
            "https://user:password@example.com/ad",
            "http://127.0.0.1/ad",
            "https://example.local/ad",
        ):
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                validate_source_url(invalid)

    def test_record_registration_validates_platform_and_date_but_allows_incomplete_notes(self):
        record = self.sample(
            source_url="",
            creative_format="",
            headline="",
            text="",
            proposition="",
            offer="",
            call_to_action="",
            destination="",
            notes="",
        )
        self.assertEqual(record["brand"], "Marca ejemplo")
        self.assertEqual(record["source_url"], "")
        self.assertEqual(record["headline"], "")
        with self.assertRaisesRegex(ValueError, "plataforma"):
            self.sample(platform="Plataforma inventada")
        with self.assertRaisesRegex(ValueError, "AAAA-MM-DD"):
            self.sample(observed_on="ayer")
        with self.assertRaisesRegex(ValueError, "marca"):
            self.sample(brand="")

    def test_search_filters_query_platform_brand_and_date(self):
        records = [
            self.sample(id="one"),
            self.sample(
                id="two",
                brand="Otra marca",
                platform="Google",
                observed_on="2026-10-13",
                headline="Oferta especial",
            ),
        ]
        found = search_observations(
            records,
            query="especial",
            platform="Google",
            brand="otra",
            start_date="2026-10-13",
            end_date="2026-10-13",
        )
        self.assertEqual([record["id"] for record in found], ["two"])
        self.assertEqual(search_observations(records, query="no existe"), [])

    def test_comparison_returns_observation_fields_without_performance_metrics(self):
        first = self.sample(id="one")
        second = self.sample(id="two", platform="TikTok", headline="Otro titular")
        compared = compare_observations(first, second)
        fields = {row["Campo"] for row in compared}
        self.assertIn("Headline", fields)
        self.assertNotIn("Spend", fields)
        headline = next(row for row in compared if row["Campo"] == "Headline")
        self.assertEqual(headline["Primera observación"], first["headline"])
        self.assertEqual(headline["Segunda observación"], second["headline"])

    def test_json_export_import_round_trips_observations_and_rejects_bad_payloads(self):
        records = [self.sample(id="record-1"), self.sample(id="record-2", source_url="")]
        exported = export_observations_json(records)
        payload = json.loads(exported)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(import_observations_json(exported), records)
        self.assertEqual(import_observations_json(exported.encode("utf-8")), records)
        with self.assertRaisesRegex(ValueError, "versión"):
            import_observations_json('{"schema_version": 2, "observations": []}')
        with self.assertRaisesRegex(ValueError, "lista"):
            import_observations_json('{"schema_version": 1, "observations": {}}')
        with self.assertRaisesRegex(ValueError, "leer"):
            import_observations_json("not json")

    def test_csv_export_contains_observation_fields_and_handles_commas(self):
        records = [self.sample(notes="Nota, con coma")]
        parsed = list(csv.DictReader(io.StringIO(export_observations_csv(records))))
        self.assertEqual(parsed[0]["brand"], "Marca ejemplo")
        self.assertEqual(parsed[0]["notes"], "Nota, con coma")
        self.assertEqual(parsed[0]["platform"], "Meta")
        self.assertNotIn("Spend", parsed[0])

    def test_analysis_handles_empty_text_and_marks_nonempty_analysis_as_hypothesis(self):
        empty = analyze_observation({"headline": "", "text": "", "offer": ""})
        self.assertEqual(empty["status"], "insufficient")
        self.assertIn("No hay texto", empty["notice"])
        analyzed = analyze_observation(
            {
                "headline": "¿Cómo ahorrar?",
                "text": "Mirá la propuesta",
                "proposition": "Ahorro",
                "offer": "2x1",
                "call_to_action": "Ver",
            }
        )
        self.assertEqual(analyzed["status"], "hypothesis")
        self.assertIn("Pregunta", analyzed["hook"])
        self.assertIn("no verifica", analyzed["notice"])
        self.assertIn("no verificada", analyzed["offer"])

    def test_official_research_source_links_are_available(self):
        self.assertEqual(
            SOURCE_URLS["Meta Ads Library"],
            "https://www.facebook.com/ads/library/",
        )
        self.assertEqual(
            SOURCE_URLS["Google Ads Transparency Center"],
            "https://adstransparency.google.com/",
        )
        self.assertEqual(
            SOURCE_URLS["TikTok Commercial Content Library"],
            "https://library.tiktok.com/",
        )


class AdVariationTests(unittest.TestCase):
    def inputs(self, **overrides):
        values = {
            "brand": "Mi marca",
            "product": "Servicio de organización",
            "audience": "personas con poco tiempo",
            "benefit": "simplificar tareas cotidianas",
            "objective": "Leads",
            "tone": "Cercano",
            "offer": "Consulta inicial sin cargo (según condiciones propias)",
        }
        values.update(overrides)
        return values

    def test_required_inputs_are_checked_before_generation(self):
        with self.assertRaisesRegex(ValueError, "beneficio principal"):
            generate_ad_variations(self.inputs(benefit=""))

    def test_generates_three_original_editable_variations_with_expected_angles(self):
        variations = generate_ad_variations(self.inputs())
        self.assertEqual(len(variations), 3)
        self.assertEqual(
            [item["angle"] for item in variations],
            ["Beneficio", "Resolver dudas", "Oferta"],
        )
        expected_fields = {
            "angle", "hook", "headline", "primary_text",
            "cta", "video_script", "reference_structure",
        }
        for variation in variations:
            self.assertTrue(expected_fields.issubset(variation))
            self.assertTrue(variation["headline"].strip())
            self.assertTrue(variation["primary_text"].strip())
    def test_empty_offer_does_not_invent_discount_or_social_proof(self):
        for offer in (
            "",
            "Dejar vac?o si no hay una promoci?n vigente",
            "No aplica",
        ):
            with self.subTest(offer=offer):
                variations = generate_ad_variations(self.inputs(offer=offer))
                self.assertEqual(
                    variations[2]["angle"],
                    "Informaci?n y condiciones",
                )
                combined = " ".join(
                    str(value)
                    for variation in variations
                    for value in variation.values()
                ).casefold()
                for forbidden in (
                    "descuento", "2x1", "testimonio", "rese?a",
                    "prueba social", "dejar vac?o", "dejar vacio",
                    "promoci?n vigente", "promocion vigente",
                ):
                    self.assertNotIn(forbidden, combined)
    def test_variations_can_be_edited_then_exported_as_csv_and_txt(self):
        variations = generate_ad_variations(self.inputs())
        variations[0]["headline"] = "Titular editado"
        csv_rows = list(csv.DictReader(io.StringIO(export_variations_csv(variations))))
        text = export_variations_txt(variations)
        self.assertEqual(csv_rows[0]["headline"], "Titular editado")
        self.assertIn("Titular: Titular editado", text)
        self.assertEqual(len(csv_rows), 3)
        self.assertIn("VARIACIÓN 3", text)

    def test_generated_copy_does_not_contain_performance_metrics_or_claims(self):
        variations = generate_ad_variations(self.inputs())
        forbidden = ("ctr", "roas", "impresiones", "ventas garantizadas", "rendimiento validado")
        rendered = export_variations_txt(variations).casefold()
        for claim in forbidden:
            self.assertNotIn(claim, rendered)


if __name__ == "__main__":
    unittest.main()
