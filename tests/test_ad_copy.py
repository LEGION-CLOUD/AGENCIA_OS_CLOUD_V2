import unittest

from ad_copy import generate_ad_proposals


class AdCopyTests(unittest.TestCase):
    def test_fashion_copy_uses_short_titles_and_natural_benefits(self):
        proposals = generate_ad_proposals(
            "Colección de ropa urbana para mujer: jeans, pantalones sastreros, blazers, tops y vestidos modernos",
            "Diseños modernos, prendas versátiles, combinaciones para distintos estilos y opciones para looks casuales o elegantes",
            "Nueva colección de temporada. Sin descuentos ni precios inventados.",
            "Ventas",
        )
        self.assertEqual(len(proposals), 3)
        joined = "\n".join(proposals)
        self.assertIn("Tu próximo look empieza acá", joined)
        self.assertIn("Moda para combinar a tu manera", joined)
        self.assertIn("jeans, pantalones sastreros, blazers, tops y vestidos modernos", joined)
        self.assertNotIn("TÍTULO: ¿Buscás Colección de ropa urbana", joined)
        self.assertNotIn("Beneficios informados:", joined)
        self.assertNotIn("servicio de Diseños modernos", joined)
        self.assertNotIn("Sin descuentos ni precios inventados", joined)
        self.assertIn("Nueva colección de temporada", joined)

    def test_service_copy_keeps_installation_context(self):
        proposals = generate_ad_proposals(
            "servicio de instalacion de aire acondicionado",
            "instalación incluida",
            "",
            "Generar consultas",
        )
        self.assertEqual(len(proposals), 3)
        self.assertIn("instalación", "\n".join(proposals).lower())
        self.assertIn("Contanos qué necesitás", proposals[0])

    def test_generic_copy_does_not_put_full_description_in_title(self):
        proposals = generate_ad_proposals(
            "Curso online de fotografía: clases prácticas, composición y edición",
            "Material de práctica",
            "",
            "Reconocimiento de marca",
        )
        self.assertEqual(len(proposals), 3)
        self.assertNotIn("clases prácticas, composición y edición", proposals[0].splitlines()[1])
        self.assertIn("Conocé la propuesta.", proposals[0])


if __name__ == "__main__":
    unittest.main()
