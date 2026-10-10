"""Regression tests for verified manufacturer domains and redirects."""
import unittest
from unittest.mock import patch
from manufacturer_domain_resolver import resolve

class Response:
    def __init__(self, url, status=200):
        self.url = url
        self.status_code = status

class Session:
    def __init__(self, url):
        self.url = url
        self.calls = 0
    def get(self, *args, **kwargs):
        self.calls += 1
        return Response(self.url)

class VerificationTests(unittest.TestCase):
    @patch("manufacturer_domain_resolver.search_links", return_value=[])
    def test_old_cache_rechecked(self, search):
        session = Session("https://www.clage.de/")
        cache = {"clage": {"domain": "clage.de", "homepage": "https://www.clage.de/"}}
        domain, _, _ = resolve(session, "CLAGE", cache, "clage.de")
        self.assertEqual(domain, "clage.de")
        self.assertGreater(session.calls, 0)
        self.assertTrue(cache["clage"]["verified"])

    @patch("manufacturer_domain_resolver.search_links", return_value=[])
    def test_unrelated_redirect_rejected(self, search):
        session = Session("https://www.unrelated-shop.example/")
        domain, _, status = resolve(session, "CLAGE", {}, "clage.de")
        self.assertIn("nicht bestätigt", status)

    @patch("manufacturer_domain_resolver.search_links", return_value=[])
    def test_verified_cache_reused(self, search):
        cache = {"clage": {"domain": "clage.de", "homepage": "https://www.clage.de/",
                           "status": "Verifiziert", "verified": True}}
        session = Session("https://www.unrelated-shop.example/")
        domain, _, _ = resolve(session, "CLAGE", cache)
        self.assertEqual(domain, "clage.de")
        self.assertEqual(session.calls, 0)

if __name__ == "__main__":
    unittest.main()
