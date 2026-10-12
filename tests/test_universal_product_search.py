"""Regressionstests der universellen Hersteller- und Produktsuche."""
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from universal_product_search import (
    SearchHit, BingRSS, BraveAPI, query_for, family_class, find_candidates,
    maker_domain, maker_aliases, model_search_key, process_file,
    rank_hit, allowed_host, valid_https, normalize
)


class FakeSource:
    name="fixture"
    last_error=""
    def __init__(self,hits):self.hits=hits;self.queries=[]
    def search(self,q,limit=12):
        self.queries.append(q)
        return self.hits[:limit]


class UniversalProductSearchTest(unittest.TestCase):
    def test_own_domain_validation(self):
        self.assertTrue(allowed_host("https://pro.villeroy-boch.com/de/de/product/a",
                                     maker_aliases("Villeroy & Boch")))
        self.assertFalse(allowed_host("https://villeroy-boch.com.evil.example/p",
                                      maker_aliases("Villeroy & Boch")))
        self.assertFalse(allowed_host("https://evil-villeroy-boch.com/p",
                                      maker_aliases("Villeroy & Boch")))
        self.assertFalse(allowed_host("http://pro.villeroy-boch.com/product/a",
                                      maker_aliases("Villeroy & Boch")))
        self.assertFalse(valid_https("https://user:pass@wika.com/product/a"))

    def test_known_company_case_variants(self):
        self.assertEqual(maker_domain("Trox"),"trox.de")
        self.assertEqual(maker_domain("TROX"),"trox.de")
        self.assertEqual(maker_domain("LAUFEN"),"laufen.com")

    def test_unknown_brand_not_bogus_domain(self):
        self.assertEqual(maker_domain("Unbekannter Hersteller"),"")

    def test_build_product_queries(self):
        row={"Hersteller":"TROX","Produkt":"Brandschutzklappe","Typ / Modell":"FKRS-EU/DE/125/Z00"}
        self.assertIn('"FKRS-EU"',query_for(row))
        self.assertEqual(model_search_key("FKRS-EU/DE/125/Z00"),"FKRS-EU")
        self.assertIn("WIKA",query_for({"Hersteller":"WIKA","Produkt":"Manometer","Typ / Modell":"111.10 NG 63"}))

    def test_missing_brand_does_not_search(self):
        row={"Hersteller":"","Produkt":"Wasserfilter","Typ / Modell":""}
        src=FakeSource([SearchHit("Filter","https://www.trox.de/produkt/filter")])
        result=find_candidates(row,[src])
        self.assertEqual(result["Trefferstatus"],"Nicht recherchierbar")
        self.assertEqual(src.queries,[])

    def test_bedarfsposition_excluded(self):
        row={"Hersteller":"TROX","Produkt":"*** Bedarfsposition ohne GB","Typ / Modell":"LVS"}
        src=FakeSource([])
        result=find_candidates(row,[src])
        self.assertEqual(result["Trefferstatus"],"Bedarfsposition")
        self.assertFalse(src.queries)

    def test_no_sku_from_model(self):
        row={"Hersteller":"WIKA","Produkt":"Manometer","Typ / Modell":"111.10 NG 63"}
        src=FakeSource([SearchHit(
            title="WIKA 111.10 NG 63 Manometer",
            url="https://www.wika.com/de-de/111_10_111_12.WIKA",
            snippet="Produktinformation")])
        result=find_candidates(row,[src])
        self.assertIn("Indexkandidat",result["Trefferstatus"])
        self.assertEqual(result["Artikelnummer_automatisch"],"")
        self.assertIn("Offizielle Herstellerdomain",result["Belege"])

    def test_trox_variant_not_conflated_with_article(self):
        row={"Hersteller":"TROX","Produkt":"Brandschutzklappe","Typ / Modell":"FKRS-EU/DE/125/Z00"}
        src=FakeSource([SearchHit("TROX FKRS-EU Brandschutzklappe",
                                 "https://www.trox.de/brandschutzklappen/fkrs-eu-123")])
        result=find_candidates(row,[src])
        self.assertTrue(result["Bester_Treffer"])
        self.assertEqual(result["Artikelnummer_automatisch"],"")
        self.assertIn("Ausführung offen",result["Belege"])

    def test_unrelated_model_rejected(self):
        row={"Hersteller":"TROX","Produkt":"Brandschutzklappe","Typ / Modell":"FKRS-EU"}
        src=FakeSource([SearchHit("TROX FK2-EU Brandschutzklappe",
                                 "https://www.trox.de/brandschutzklappen/fk2-eu-123")])
        result=find_candidates(row,[src])
        self.assertEqual(result["Trefferzahl"],0)

    def test_other_manufacturer_rejected(self):
        row={"Hersteller":"WIKA","Produkt":"Manometer","Typ / Modell":"111.10"}
        src=FakeSource([SearchHit("WIKA 111.10 Manometer",
                                 "https://www.example.com/111-10-manometer")])
        self.assertEqual(find_candidates(row,[src])["Trefferzahl"],0)

    def test_indexed_partner_never_counts_manufacturer_evidence(self):
        row={"Hersteller":"WIKA","Produkt":"Manometer","Typ / Modell":"111.10"}
        source=FakeSource([SearchHit("WIKA 111.10 Manometer",
                                    "https://www.ausschreiben.de/catalog/wika/11110")])
        result=find_candidates(row,[source])
        self.assertIn("Drittanbieter",result["Trefferstatus"])
        self.assertEqual(result["Artikelnummer_automatisch"],"")

    def test_homepage_rejected(self):
        row={"Hersteller":"TROX","Produkt":"Brandschutzklappe","Typ / Modell":"FKRS-EU"}
        self.assertIsNone(rank_hit(row,SearchHit("TROX FKRS-EU","https://www.trox.de/")))

    def test_generic_sanitary_row_not_false_positive(self):
        row={"Hersteller":"Villeroy & Boch","Produkt":"WC","Typ / Modell":""}
        src=FakeSource([SearchHit("Villeroy & Boch WC",
                                 "https://pro.villeroy-boch.com/de/de/wc")])
        result=find_candidates(row,[src])
        self.assertEqual(result["Trefferzahl"],0)
        self.assertIn("Produktfamilie",result["Produktstatus"])

    def test_family_scope(self):
        x={"Hersteller":"Geberit","Produkt":"Systemrohr","Typ / Modell":"Mapress Therm"}
        self.assertEqual(family_class(x),"Produktfamilie – Auswahl erforderlich")

    def test_deduplicate_sources(self):
        row={"Hersteller":"TROX","Produkt":"Brandschutzklappe","Typ / Modell":"FKRS-EU"}
        a=SearchHit("TROX FKRS-EU Brandschutzklappe",
                    "https://www.trox.de/brandschutzklappen/fkrs-eu-123")
        result=find_candidates(row,[FakeSource([a,a]),FakeSource([a])])
        self.assertEqual(result["Trefferzahl"],1)

    def test_bing_rss_parses_real_xml(self):
        xml=b"""<?xml version="1.0"?><rss version="2.0"><channel><item>
        <title>TROX FKRS-EU Brandschutzklappe</title>
        <link>https://www.trox.de/brandschutzklappen/fkrs-eu-123</link>
        <description>Produktdaten</description>
        </item></channel></rss>"""
        response=Mock(status_code=200,content=xml)
        sess=Mock();sess.get.return_value=response
        provider=BingRSS(sess)
        hits=provider.search("TROX FKRS-EU")
        self.assertEqual(len(hits),1)
        self.assertEqual(hits[0].provider,"bing_rss")

    def test_bing_html_challenge_is_not_rss(self):
        response=Mock(status_code=200,content=b"<html>Just a moment...</html>")
        sess=Mock();sess.get.return_value=response
        p=BingRSS(sess)
        self.assertEqual(p.search("WIKA"),[])
        self.assertEqual(p.last_error,"Keine RSS-Antwort")

    def test_brave_without_key_never_posts(self):
        sess=Mock()
        p=BraveAPI("",sess)
        self.assertEqual(p.search("WIKA"),[])
        sess.get.assert_not_called()

    def test_csv_keeps_all_rows_without_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"in.csv";out=Path(folder)/"out.csv"
            source.write_text("ID;Hersteller;Produkt;Typ / Modell\n1;TROX;Brandschutzklappe;FKRS-EU\n2;WIKA;Manometer;111.10\n3;;Gerät;\n",encoding="utf-8")
            result=process_file(source,out,provider="offline",delay=0)
            self.assertEqual(result["datensaetze"],3)
            self.assertEqual(result["automatisch_belegte_artikelnummern"],0)
            with out.open(encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f,delimiter=";"))
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[1]["Artikelnummer_automatisch"],"")
            self.assertEqual(rows[2]["Trefferstatus"],"Nicht recherchierbar")


if __name__=="__main__":
    unittest.main()
