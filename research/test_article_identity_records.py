import unittest
from research.article_identity_records import codes, extract_html_records, classify

class IdentityTests(unittest.TestCase):
    def test_reject_label(self):
        self.assertEqual(codes("Artikelnummer: Einbaudatum"), [])
    def test_extract_helios(self):
        self.assertEqual(codes("Artikelnummer: 09506"), ["09506"])
    def test_model_scoping(self):
        html = "<table><tr><td>SB 125 A</td><td>Artikelnummer: 09506</td></tr><tr><td>SB 160 A</td><td>Artikelnummer: 09507</td></tr></table>"
        self.assertEqual(extract_html_records(html, model="SB 125 A"), [("09506", "table-row")])
    def test_dimension_scoping(self):
        html = "<table><tr><td>Mapress Muffe 15 mm</td><td>Artikelnummer: 12345</td></tr><tr><td>Mapress Muffe 22 mm</td><td>Artikelnummer: 67890</td></tr></table>"
        self.assertEqual(extract_html_records(html, model="Muffe", dimension="22 mm"), [("67890", "table-row")])
    def test_jsonld(self):
        html = '<script type="application/ld+json">{"@type":"Product","name":"SB 125 A","sku":"09506"}</script>'
        self.assertEqual(extract_html_records(html, model="SB 125 A"), [("09506", "product-jsonld")])
    def test_ambiguous(self):
        self.assertEqual(classify([("1","row"),("2","row")]), "mehrdeutig")
    def test_not_confirmed(self):
        self.assertIn("offen", classify([("09506","row")]))
    def test_no_pagewide_match(self):
        html = "<h1>SB 125 A</h1><p>Artikelnummer: 09506</p>"
        self.assertEqual(extract_html_records(html, model="SB 125 A"), [])
if __name__ == "__main__":
    unittest.main()
