"""Regression checks for manufacturer article source matching."""
import unittest
from headless_article_research import domain_for,seeded_urls,documented_candidates
from manufacturer_article_engine import source_records

class ArticleSourceTests(unittest.TestCase):
 def test_domain_aliases(self):
  self.assertEqual(domain_for("IMI Heimeier"),"imi-hydronic.com")
  self.assertEqual(domain_for("Villeroy & Boch"),"villeroy-boch.de")
  self.assertEqual(domain_for("CLAGE GmbH"),"clage.de")
 def test_known_official_source(self):
  self.assertTrue(any("pa-10-01735" in u for u in seeded_urls("Helios","Drehzahl-Potentiometer","PA 10")))
  self.assertFalse(seeded_urls("Helios","Drehzahl-Potentiometer","PA 12"))
 def test_local_label_number(self):
  html="<h1>PA 10</h1><table><tr><th>Artikelnummer</th><td>01735</td></tr><tr><th>Artikeltype</th><td>PA 10</td></tr></table>"
  self.assertIn(("01735","Produktdetail"),source_records(html,model="PA 10"))
 def test_official_document_evidence(self):
  self.assertEqual(documented_candidates("emco","emco art 1675 001 00 chrom","")[0][0],"1675 001 00")
  self.assertEqual(documented_candidates("Jung Pumpen","Jung Pumpen U3K","U3K")[0][0],"JP50002")
  self.assertEqual(documented_candidates("Jung Pumpen","U5K","U5K"),[])
 def test_no_model_as_article(self):
  html="<h1>PA 10</h1><p>Artikeltype: PA 10</p>"
  self.assertEqual(source_records(html,model="PA 10"),[])

if __name__=="__main__":unittest.main()
