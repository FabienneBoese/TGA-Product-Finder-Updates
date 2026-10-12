"""Regression tests: an HTTP 200 must never be enough to confirm an article."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from verify_product_candidates import verify_one,verify_row,verify_file


def response(url,code=200,text="<html><title>FKRS-EU | TROX</title><h1>FKRS-EU</h1></html>",
             ctype="text/html",location=""):
    headers={"Content-Type":ctype}
    if location:headers["Location"]=location
    return Mock(status_code=code,url=url,text=text,content=text.encode("utf-8"),
                headers=headers)


class CandidateVerificationTest(unittest.TestCase):
    def setUp(self):
        self.trox={"Hersteller":"TROX","Produkt":"Brandschutzklappe",
                   "Typ / Modell":"FKRS-EU/DE/125/Z00"}
        self.url="https://www.trox.de/brandschutzklappen/fkrs-eu-123"

    def test_model_family_not_sku(self):
        sess=Mock();sess.get.return_value=response(self.url)
        result=verify_one(self.trox,self.url,sess)
        self.assertEqual(result["http"],"200")
        self.assertIn("Produktfamilie",result["status"])

    def test_full_model_in_title(self):
        sess=Mock();sess.get.return_value=response(
            self.url,text="<title>TROX FKRS-EU/DE/125/Z00</title>")
        self.assertIn("Produkttyp",verify_one(self.trox,self.url,sess)["status"])

    def test_unrelated_model_http_200_not_product(self):
        sess=Mock();sess.get.return_value=response(
            self.url,text="<title>TROX FK2-EU</title><h1>FK2-EU</h1>")
        self.assertIn("nicht bestätigt",verify_one(self.trox,self.url,sess)["status"])

    def test_http_403_not_success(self):
        sess=Mock();sess.get.return_value=response(self.url,403,"Just a moment")
        result=verify_one(self.trox,self.url,sess)
        self.assertEqual(result["http"],"403")
        self.assertNotIn("bestätigt",result["status"])

    def test_cloudflare_interstitial_200_not_success(self):
        sess=Mock();sess.get.return_value=response(self.url,200,"<html>Just a moment... cf-chl</html>")
        self.assertIn("Sperre",verify_one(self.trox,self.url,sess)["status"])

    def test_offdomain_link_never_fetched(self):
        sess=Mock()
        result=verify_one(self.trox,"https://www.trox.de.bad.example/abc",sess)
        self.assertEqual(result["status"],"Kein freigegebener Herstellerlink")
        sess.get.assert_not_called()

    def test_offdomain_redirect_never_followed(self):
        sess=Mock()
        sess.get.return_value=response(self.url,302,location="https://evil.example/steal")
        result=verify_one(self.trox,self.url,sess)
        self.assertIn("Fremddomain",result["status"])
        self.assertEqual(sess.get.call_count,1)

    def test_intra_maker_redirect_followed(self):
        sess=Mock()
        sess.get.side_effect=[
            response(self.url,301,location="/de/brandschutzklappen/fkrs-eu-1"),
            response("https://www.trox.de/de/brandschutzklappen/fkrs-eu-1")]
        result=verify_one(self.trox,self.url,sess)
        self.assertIn("Produktfamilie",result["status"])
        self.assertEqual(sess.get.call_count,2)

    def test_no_model_requires_two_product_keywords(self):
        row={"Hersteller":"Duravit","Produkt":"Brauseset Badewanne","Typ / Modell":""}
        sess=Mock()
        url="https://www.duravit.de/produkte/badewannen"
        sess.get.return_value=response(url,text="<h1>Duravit Badewannen</h1>")
        self.assertIn("unbestätigt",verify_one(row,url,sess)["status"])

    def test_row_promotes_evidenced_family_without_article_number(self):
        sess=Mock();sess.get.return_value=response(self.url)
        row=dict(self.trox,Kandidaten_JSON=json.dumps([{"url":self.url,
                                      "source_kind":"Herstellerdomain"}]))
        out=verify_row(row,sess)
        self.assertEqual(out["Produktseiten_Bestaetigt"],"Ja")
        self.assertEqual(out["Produktseiten_HTTP"],"200")
        self.assertEqual(out["Produktseiten_Verifizierte_URL"],self.url)

    def test_index_partner_skipped_even_with_high_score(self):
        sess=Mock()
        row=dict(self.trox,Kandidaten_JSON=json.dumps([{"url":"https://www.oxomi.com/p",
                                       "source_kind":"Zentrales Verzeichnis"}]))
        out=verify_row(row,sess)
        self.assertEqual(out["Produktseiten_Bestaetigt"],"Nein")
        sess.get.assert_not_called()


if __name__=="__main__":
    unittest.main()
