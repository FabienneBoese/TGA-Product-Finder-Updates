"""Unit tests for manufacturer discovery without network access."""
import unittest
from unittest.mock import patch
from manufacturer_domain_resolver import resolve, plausible

class Response:
    status_code = 200
    url = "https://www.clage.de/"
    text = "<html><title>CLAGE</title></html>"

class Session:
    def get(self, url, **kwargs):
        return Response()

class ResolverTests(unittest.TestCase):
    def test_plausible_official_domain(self):
        self.assertTrue(plausible("CLAGE", "https://www.clage.de/"))
        self.assertFalse(plausible("CLAGE", "https://www.amazon.de/clage"))
    @patch("manufacturer_domain_resolver.search_links", return_value=["https://www.clage.de/"])
    def test_new_manufacturer_without_domain_mapping(self, search):
        cache = {}
        domain, homepage, status = resolve(Session(), "CLAGE", cache)
        self.assertEqual(domain, "clage.de")
        self.assertEqual(homepage, "https://www.clage.de/")
        self.assertIn("clage", cache)
    @patch("manufacturer_domain_resolver.search_links", return_value=[])
    def test_known_domain_fallback_is_unverified(self, search):
        class Offline:
            def get(self, *args, **kwargs):
                raise __import__("requests").Timeout()
        domain, homepage, status = resolve(Offline(), "CLAGE", {}, "clage.de")
        self.assertEqual(domain, "clage.de")
        self.assertIn("nicht bestätigt", status)

if __name__ == "__main__":
    unittest.main()
