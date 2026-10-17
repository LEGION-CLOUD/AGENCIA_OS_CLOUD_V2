import unittest

import app


class CompetitorSectorDetectionTests(unittest.TestCase):
    def assert_sector(self, brand, expected):
        result = app.analisis_real_diferenciado(brand)
        self.assertIn(f"Rubro estimado: {expected}", result)

    def test_nvidia_is_technology_not_supermarket(self):
        self.assert_sector("NVIDIA", "TECH")

    def test_short_tech_brand_lg_is_detected(self):
        self.assert_sector("LG", "TECH")

    def test_samsung_is_technology(self):
        self.assert_sector("Samsung", "TECH")

    def test_accented_fravega_is_technology(self):
        self.assert_sector("Frávega", "TECH")

    def test_coto_is_supermarket(self):
        self.assert_sector("Coto", "SUPERMERCADO")

    def test_zara_is_fashion(self):
        self.assert_sector("Zara", "MODA")


if __name__ == "__main__":
    unittest.main()
