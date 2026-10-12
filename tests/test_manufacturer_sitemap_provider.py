"""Tests for generic public manufacturer sitemap provider."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from manufacturer_sitemap_provider import OfficialSitemap,parse_sitemap
from universal_product_search import find_candidates


def fake_resp(content,url,code=200):
    return Mock(status_code=code,content=content,url=url)


class SitemapProviderTests(unittest.TestCase):
    def test_simple_sitemap_and_namespace(self):
        xml=b"""<?xml version='1.0'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
        <url><loc>https://www.trox.de/brandschutzklappen/fkrs-eu-123</loc></url>
        </urlset>"""
        kind,urls=parse_sitemap(xml)
        self.assertEqual(kind,"urlset")
        self.assertEqual(urls,["https://www.trox.de/brandschutzklappen/fkrs-eu-123"])

    def test_sitemap_index(self):
        xml=b"""<sitemapindex><sitemap><loc>https://www.geberit.de/sitemap-de-de.xml</loc>
        </sitemap></sitemapindex>"""
        self.assertEqual(parse_sitemap(xml)[0],"sitemapindex")

    def test_html_challenge_never_accepted(self):
        self.assertEqual(parse_sitemap(b"<html>Just a moment...</html>"),("",[]))

    def test_generic_trox_model_search(self):
        calls=[]
        xml=b"""<urlset>
        <url><loc>https://www.trox.de/brandschutzklappen/fkrs-eu-123</loc></url>
        <url><loc>https://www.trox.de/brandschutzklappen/fk2-eu-223</loc></url>
        <url><loc>https://trox.de/kontakt</loc></url>
        </urlset>"""
        session=Mock()
        def get(url,**kwargs):
            calls.append(url)
            if url.endswith("/robots.txt"):return fake_resp(b"User-agent: *\n",url)
            if url.endswith("/sitemap.xml"):return fake_resp(xml,url)
            return fake_resp(b"missing",url,404)
        session.get.side_effect=get
        p=OfficialSitemap(session)
        row={"Hersteller":"TROX","Produkt":"Brandschutzklappe",
             "Typ / Modell":"FKRS-EU/DE/125/Z00"}
        hits=p.search_for(row)
        self.assertEqual(len(hits),1)
        self.assertIn("fkrs-eu",hits[0].url)
        out=find_candidates(row,[p])
        self.assertEqual(out["Trefferzahl"],1)
        self.assertIn("Offizieller Sitemap-Eintrag",out["Trefferstatus"])
        self.assertEqual(out["Artikelnummer_automatisch"],"")
        self.assertEqual(calls.count("https://www.trox.de/sitemap.xml"),1)

    def test_bare_manufacturer_homepage_not_product(self):
        xml=b"<urlset><url><loc>https://www.trox.de/</loc></url></urlset>"
        session=Mock()
        session.get.side_effect=lambda url,**kw:fake_resp(
            b"" if url.endswith("robots.txt") else xml,url)
        p=OfficialSitemap(session)
        out=find_candidates({"Hersteller":"TROX","Produkt":"Brandschutzklappe",
                             "Typ / Modell":"FKRS-EU"},[p])
        self.assertEqual(out["Trefferzahl"],0)

    def test_robots_off_domain_sitemap_ignored(self):
        xml=b"""<urlset><url><loc>https://evil.example/catalog/fkrs-eu</loc></url>
        <url><loc>https://www.trox.de/brandschutzklappen/fkrs-eu</loc></url></urlset>"""
        session=Mock()
        def get(url,**kwargs):
            if url.endswith("robots.txt"):
                return fake_resp(b"Sitemap: https://evil.example/hijack.xml\n",url)
            return fake_resp(xml,url)
        session.get.side_effect=get
        p=OfficialSitemap(session)
        result=p.search_for({"Hersteller":"TROX","Produkt":"Brandschutzklappe",
                             "Typ / Modell":"FKRS-EU"})
        self.assertEqual(len(result),1)
        self.assertFalse(any("evil.example" in call.args[0] for call in session.get.call_args_list))

    def test_redirect_outside_manufacturer_discarded(self):
        session=Mock()
        def get(url,**kw):
            return fake_resp(b"<urlset><url><loc>https://www.trox.de/fkrs-eu</loc></url></urlset>",
                             "https://unrelated.example/fake")
        session.get.side_effect=get
        p=OfficialSitemap(session)
        self.assertEqual(p.search_for({"Hersteller":"TROX","Produkt":"Brandschutzklappe",
                                       "Typ / Modell":"FKRS-EU"}),[])

    def test_cache_shared_across_brand_variants(self):
        count=[]
        session=Mock()
        def get(url,**kwargs):
            count.append(url)
            if url.endswith("robots.txt"):return fake_resp(b"",url)
            return fake_resp(b"<urlset><url><loc>https://www.trox.de/fkrs-eu</loc></url></urlset>",url)
        session.get.side_effect=get
        p=OfficialSitemap(session)
        for maker in ["TROX","Trox"]:
            p.search_for({"Hersteller":maker,"Produkt":"Brandschutzklappe","Typ / Modell":"FKRS-EU"})
        self.assertEqual(sum(x.endswith("sitemap.xml") for x in count),1)

    def test_no_company_fallback(self):
        p=OfficialSitemap(Mock())
        self.assertEqual(p.search_for({"Hersteller":"Nonexistent new manufacturer",
                                        "Produkt":"Test","Typ / Modell":"123"}),[])
        self.assertIn("Domain",p.last_error)


if __name__=="__main__":
    unittest.main()
