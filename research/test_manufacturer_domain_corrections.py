import unittest
from unittest.mock import patch
from manufacturer_domain_resolver import resolve, KNOWN_MANUFACTURER_DOMAINS, allowed_redirect

class Response:
    status_code=200
    def __init__(self,url): self.url=url

class Session:
    def get(self,url,**kwargs):
        if "schedel-badinnovation.de" in url: return Response("https://schedel-badinnovation.de/")
        if "wittigsthal.de" in url: return Response("https://www.wittigsthal.de/")
        raise AssertionError("Wrong domain: "+url)

class Corrections(unittest.TestCase):
    @patch("manufacturer_domain_resolver.search_links",return_value=[])
    def test_corrected_domains(self,_):
        for maker,expected in (("Schedel","schedel-badinnovation.de"),("Wittingsthal","wittigsthal.de")):
            cache={}
            domain,_,_=resolve(Session(),maker,cache)
            self.assertEqual(domain,expected)
            self.assertTrue(cache[maker.casefold()]["verified"])
    def test_duravit_redirect(self):
        self.assertTrue(allowed_redirect("duravit.de","duravit.com"))
        self.assertFalse(allowed_redirect("duravit.de","untrusted.example"))
if __name__=="__main__": unittest.main()
