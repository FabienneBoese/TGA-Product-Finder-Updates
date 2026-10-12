"""No live manufacturer requests. Validate entitlement gates and machine source logic."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
from authorized_manufacturer_sources import (
    oxomi_access_token, oxomi_product_data, parse_bmecat, planned_access
)


class AuthorizedManufacturerSourcesTest(unittest.TestCase):
    def test_bmecat_2005_product(self):
        xml = b"""<?xml version="1.0"?><BMECAT><T_NEW_CATALOG>
        <PRODUCT><SUPPLIER_PID>111.10</SUPPLIER_PID><PRODUCT_DETAILS>
        <DESCRIPTION_SHORT>Manometer</DESCRIPTION_SHORT>
        <MANUFACTURER_NAME>WIKA</MANUFACTURER_NAME></PRODUCT_DETAILS>
        </PRODUCT></T_NEW_CATALOG></BMECAT>"""
        items = parse_bmecat(xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["artikelnummer"], "111.10")
        self.assertEqual(items[0]["bezeichnung"], "Manometer")

    def test_bmecat_12_article_namespace(self):
        xml = """<BMECAT xmlns="urn:bmecat"><T_NEW_CATALOG><ARTICLE>
        <SUPPLIER_AID>ABC-1</SUPPLIER_AID>
        <ARTICLE_DETAILS><DESCRIPTION_SHORT>Testartikel</DESCRIPTION_SHORT></ARTICLE_DETAILS>
        </ARTICLE></T_NEW_CATALOG></BMECAT>"""
        self.assertEqual(parse_bmecat(xml)[0]["artikelnummer"], "ABC-1")

    def test_bmecat_ignores_missing_id(self):
        self.assertEqual(parse_bmecat("<BMECAT><ARTICLE><ARTICLE_DETAILS/></ARTICLE></BMECAT>"), [])

    def test_reject_xml_entities(self):
        bad = '<!DOCTYPE foo [<!ENTITY x "INJECTION">]><BMECAT><ARTICLE>&x;</ARTICLE></BMECAT>'
        with self.assertRaises(Exception):
            parse_bmecat(bad)

    def test_wika_only_counts_actual_authorized_data(self):
        self.assertEqual(planned_access("WIKA").status, "FREIGABE_AUSSTEHEND")
        with tempfile.TemporaryDirectory() as folder:
            catalog = Path(folder) / "wika.xml"
            catalog.write_text(
                '<BMECAT><PRODUCT><SUPPLIER_PID>W-1</SUPPLIER_PID></PRODUCT></BMECAT>',
                encoding="utf-8")
            result = planned_access("WIKA", wika_catalog=str(catalog))
            self.assertEqual(result.status, "KATALOG_BEREIT")
            self.assertIn("1 Katalogartikel", result.reason)

    def test_villeroy_requires_portal_entitlement(self):
        self.assertEqual(planned_access("Villeroy & Boch").status, "FREIGABE_AUSSTEHEND")
        self.assertEqual(planned_access("Villeroy & Boch",
                         oxomi_portal="1234").status, "FREIGABE_AUSSTEHEND")
        result = planned_access("Villeroy & Boch",
                                oxomi_portal="1234", oxomi_approved=True)
        self.assertEqual(result.status, "API_KONFIGURIERT_NICHT_LIVE_GETESTET")

    def test_oxomi_token_scheme(self):
        secret, portal, user, day = "TEST_SECRET", "111", "user", 12345
        inner = hashlib.md5((secret+portal+user+str(day)).encode()).hexdigest()
        expected = hashlib.md5((secret+inner).encode()).hexdigest()
        self.assertEqual(oxomi_access_token(secret,portal,user,day), expected)

    def test_oxomi_never_posts_without_entitlement(self):
        session=Mock()
        with self.assertRaises(PermissionError):
            oxomi_product_data(session,portal="111",user="user",secret="abc",
                               supplier_number="WI",item_number="123",
                               epoch_days=12345)
        session.post.assert_not_called()

    def test_oxomi_strict_product_match(self):
        response=Mock(status_code=200)
        response.json.return_value={"success":True,"products":[
            {"resolved":True,"supplierNumber":"WRONG","itemNumber":"123"},
            {"resolved":True,"supplierNumber":"VB","itemNumber":"123"}]}
        session=Mock()
        session.post.return_value=response
        result=oxomi_product_data(session,portal="111",user="user",secret="abc",
                                  supplier_number="VB",item_number="123",
                                  epoch_days=12345,access_approved=True)
        self.assertEqual(len(result["products"]),1)
        self.assertTrue(result["matched"])
        endpoint=session.post.call_args.args[0]
        self.assertEqual(endpoint, "https://oxomi.com/portals/api/v2/product/data")
        self.assertIn("accessToken",session.post.call_args.kwargs["params"])

    def test_oxomi_unauthorized_response_never_success(self):
        response=Mock(status_code=403)
        session=Mock()
        session.post.return_value=response
        with self.assertRaises(PermissionError):
            oxomi_product_data(session,portal="111",user="user",secret="abc",
                               supplier_number="VB",item_number="123",
                               epoch_days=12345,access_approved=True)

    def test_existing_manufacturer_untouched(self):
        self.assertEqual(planned_access("TROX").status,"NICHT_IN_DIESEM_MODUL")


if __name__ == "__main__":
    unittest.main()
