"""Deterministic regression tests; no external HTTP calls."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
from manufacturer_website_check import candidate_urls, check_manufacturer, permitted_host, probe

class FakeResponse:
    def __init__(self, url, code=200, text="<html><title>Hersteller</title></html>", mime="text/html"):
        self.url, self.status_code, self.text = url, code, text
        self.headers = {"Content-Type": mime}

class ManufacturerWebsiteTest(unittest.TestCase):
    def test_reject_lookalike_domain(self):
        self.assertFalse(permitted_host("trox.de.evil.example", ["trox.de"]))
        self.assertTrue(permitted_host("shop.trox.de", ["trox.de"]))
        self.assertFalse(permitted_host("fake-trox.de", ["trox.de"]))

    def test_redirect_to_foreign_domain_is_not_verified(self):
        s = Mock()
        s.get.return_value = FakeResponse("https://wrong-domain.example/")
        found, message = probe(s, "https://www.trox.de/", ["trox.de"])
        self.assertIsNone(found)
        self.assertIn("Fremdweiterleitung", message)

    def test_http_403_is_not_reachable(self):
        s = Mock()
        s.get.return_value = FakeResponse("https://www.trox.de/", 403)
        self.assertIsNone(probe(s, "https://www.trox.de/", ["trox.de"])[0])

    def test_bot_challenge_is_not_reachable(self):
        s = Mock()
        s.get.return_value = FakeResponse("https://www.trox.de/", text="<html>Just a moment...</html>")
        self.assertIsNone(probe(s, "https://www.trox.de/", ["trox.de"])[0])

    def test_official_regional_redirect_is_valid(self):
        s = Mock()
        s.get.return_value = FakeResponse("https://www.duravit.com/de-de/")
        found, _ = probe(s, "https://www.duravit.de/", ["duravit.de", "duravit.com"])
        self.assertEqual(found, "https://www.duravit.com/de-de/")

    def test_known_official_domain_overrides_old_cache(self):
        s = Mock()
        s.get.return_value = FakeResponse("https://www.heliosventilatoren.de/de/")
        result = check_manufacturer(s, "Helios")
        self.assertEqual(result["Website-erreichbar"], "Ja")
        self.assertEqual(result["Herstellerdomain"], "heliosventilatoren.de")
        self.assertFalse(any("helios1909" in call.args[0] for call in s.get.call_args_list))

    def test_no_manufacturer_never_guessed(self):
        s = Mock()
        result = check_manufacturer(s, "")
        self.assertEqual(result["Herstellerwebsite-Status"], "Hersteller fehlt")
        s.get.assert_not_called()

    def test_no_unrelated_search_or_product_page_calls(self):
        s = Mock()
        s.get.return_value = FakeResponse("https://www.geberit.de/")
        check_manufacturer(s, "Geberit")
        self.assertTrue(all("/search" not in call.args[0] and "/product" not in call.args[0]
                            for call in s.get.call_args_list))

    def test_country_path_fallbacks(self):
        self.assertIn("https://www.heliosventilatoren.de/de/", candidate_urls("heliosventilatoren.de"))

if __name__ == "__main__":
    unittest.main()
