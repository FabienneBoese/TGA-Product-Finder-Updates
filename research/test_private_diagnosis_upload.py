import tempfile
import unittest
from pathlib import Path
from research.private_diagnosis_upload import diagnosis_csv,save_diagnosis,upload_diagnosis
class Fake:
 def __init__(self,status):self.status_code=status
class Session:
 def __init__(self,status=201):self.status=status;self.kw=None
 def put(self,url,**kw):self.kw=(url,kw);return Fake(self.status)
class TestPrivateDiagnosis(unittest.TestCase):
 def test_csv_and_local(self):
  with tempfile.TemporaryDirectory() as d:
   p=save_diagnosis([{"ID":8,"Artikelnummern-Kandidaten":"09506","Status":"Ein Kandidat"}],d)
   self.assertTrue(p.exists())
   self.assertIn("09506",p.read_text(encoding="utf-8-sig"))
 def test_upload_private_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=save_diagnosis([{"ID":8}],d)
   s=Session()
   url=upload_diagnosis(p,"test_token",session=s)
   self.assertIn("TGA-Product-Finder-Diagnose",url)
   self.assertIn("/contents/diagnosen/",s.kw[0])
   self.assertNotIn("test_token",str(s.kw[0]))
   with self.assertRaises(ValueError):upload_diagnosis(p,"test_token",repository="FabienneBoese/TGA-Product-Finder-Updates",session=s)
 def test_no_token(self):
  with tempfile.TemporaryDirectory() as d:
   p=save_diagnosis([{"ID":1}],d)
   with self.assertRaises(ValueError):upload_diagnosis(p,"")
 def test_failed_upload_preserves_file(self):
  with tempfile.TemporaryDirectory() as d:
   p=save_diagnosis([{"ID":1}],d)
   with self.assertRaises(RuntimeError):upload_diagnosis(p,"token",session=Session(403))
   self.assertTrue(p.exists())
if __name__=="__main__":unittest.main()
