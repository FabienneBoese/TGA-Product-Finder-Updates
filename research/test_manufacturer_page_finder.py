"""Regression checks for independent manufacturer-page search."""
import unittest
from unittest.mock import patch
from manufacturer_page_finder import classify

class FakeSession:
    def get(self, url, **kwargs):
        class Response:
            status_code = 200
            headers = {"Content-Type": "text/html"}
            text = "<html><title>SB 125 A Silentbox</title><h1>SB 125 A</h1></html>"
        response = Response()
        response.url = url
        return response

class ManufacturerFinderTests(unittest.TestCase):
    def test_missing_manufacturer(self):
        result = classify(FakeSession(), {"Hersteller": "", "Produkt": "WC", "Typ / Modell": ""})
        self.assertEqual(result["Suchstatus"], "Hersteller fehlt")
    @patch("manufacturer_page_finder.discover")
    def test_official_page_candidate(self, discover):
        url = "https://www.heliosventilatoren.de/de/produkte/boxventilatoren/silentbox/sb-125-a-09506"
        discover.return_value = ([url], "")
        result = classify(FakeSession(), {"Hersteller": "Helios", "Produkt": "Ventilatorbox", "Typ / Modell": "SB 125 A"})
        self.assertEqual(result["Produktseiten-URL"], url)
        self.assertIn("Prüfung", result["Suchstatus"])
    @patch("manufacturer_page_finder.discover")
    def test_unverified_official_links(self, discover):
        discover.return_value = (["https://www.heliosventilatoren.de/"], "")
        result = classify(FakeSession(), {"Hersteller": "Helios", "Produkt": "Ventilatorbox", "Typ / Modell": "SB 125 A"})
        self.assertEqual(result["Produktseiten-URL"], "")
        self.assertIn("unbestätigt", result["Suchstatus"])

if __name__ == "__main__":
    unittest.main()
