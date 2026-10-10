"""Universal redirect and verification regression tests."""
import unittest
from unittest.mock import patch
from manufacturer_domain_resolver import allowed_redirect, resolve

class Response:
    status_code = 200
    url = "https://www.clage.com/de"

class Session:
    def get(self, *args, **kwargs):
        return Response()

class UniversalRedirectTests(unittest.TestCase):
    def test_reviewed_redirects(self):
        for old, new in (("grohe.de","grohe.com"), ("clage.de","clage.com"),
                         ("hewi.de","hewi.com"), ("imi-hydronic.com","imiplc.com"),
                         ("alape.com","laufen.com")):
            self.assertTrue(allowed_redirect(old,new))
        self.assertFalse(allowed_redirect("clage.de","fake-clage.com"))
        self.assertFalse(allowed_redirect("clage.de","clage.com.evil.test"))

    @patch("manufacturer_domain_resolver.search_links", return_value=[])
    def test_known_manufacturer_redirect_is_cached_as_reviewed(self, search):
        cache={}
        domain, url, status=resolve(Session(),"CLAGE",cache,"clage.de")
        self.assertEqual(domain,"clage.com")
        self.assertTrue(cache["clage"]["verified"])

    @patch("manufacturer_domain_resolver.search_links", return_value=["https://www.clage.de/"])
    def test_search_only_result_does_not_become_verified(self, search):
        cache={}
        domain, url, status=resolve(Session(),"CLAGE",cache)
        self.assertEqual(domain,"clage.com")
        self.assertFalse(cache["clage"]["verified"])

if __name__=="__main__":
    unittest.main()
