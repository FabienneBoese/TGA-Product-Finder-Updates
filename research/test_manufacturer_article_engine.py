import unittest
from research.manufacturer_article_engine import source_records,pdf_records,classify_hits
class TestArticleEngine(unittest.TestCase):
 def test_helios_product_detail(self):
  h='<h1>SB 125 A</h1><table><tr><td>Artikelnummer:</td><td>09506</td></tr><tr><td>Spannung</td><td>230 V</td></tr></table>'
  self.assertIn(('09506','Produktdetail'),source_records(h,'SB 125 A'))
 def test_helios_family_row(self):
  h='<table><tr><td>09506</td><td>SB 125 A</td><td>230</td></tr><tr><td>09562</td><td>SB 125 C</td><td>440</td></tr></table>'
  self.assertEqual(source_records(h,'SB 125 A'),[('09506','Produktzeile')])
 def test_ambiguous(self):
  self.assertIn('Mehrere',classify_hits([('12345','a'),('67890','b')]))
 def test_pdf_model(self):
  t='SB 125 A 09506 230 1130\nSB 125 C 09562 440 1850'
  self.assertEqual(pdf_records(t,'SB 125 A'),[('09506','PDF-Katalogzeile')])
if __name__=='__main__':unittest.main()
