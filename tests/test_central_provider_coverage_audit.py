import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from central_provider_coverage_audit import normalize_maker,audit_rows,audit_file


class CentralProviderAuditTest(unittest.TestCase):
    def test_case_variants_collapse(self):
        self.assertEqual(normalize_maker("TROX"),normalize_maker("Trox"))
        self.assertEqual(normalize_maker("LAUFEN"),normalize_maker("Laufen"))

    def test_known_arge_membership_is_only_brand_evidence(self):
        row=audit_rows([{"Hersteller":"Geberit","Produkt":"Duofix","Typ / Modell":""}])[0]
        self.assertEqual(row["ARGE_Marke_in_publizierten_Beispielen"],"Ja")
        self.assertEqual(row["Zentrale_Produktquelle_live_bestaetigt"],"Nein")
        self.assertIn("Nicht geprüft",row["ARGE_Produkt_nachgewiesen"])

    def test_unlisted_not_mistaken_as_absent(self):
        row=audit_rows([{"Hersteller":"WIKA","Produkt":"Manometer"}])[0]
        self.assertEqual(row["ARGE_Marke_in_publizierten_Beispielen"],"Nicht im Beispielnachweis")
        self.assertEqual(row["Zentrale_Produktquelle_live_bestaetigt"],"Nein")

    def test_no_manufacturer_not_counted(self):
        row=audit_rows([{"Hersteller":"","Produkt":"Speicherladesystem"}])[0]
        self.assertEqual(row["Datenstatus"],"Hersteller fehlt")
        self.assertEqual(row["ARGE_Produkt_nachgewiesen"],"Hersteller fehlt")

    def test_normalization_aliases(self):
        self.assertEqual(normalize_maker("Witingsthal"),"wittigsthal")
        self.assertEqual(normalize_maker("CLAGE GmbH"),"clage")

    def test_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"in.csv";out=Path(d)/"out.csv"
            inp.write_text("ID;Hersteller;Produkt;Typ / Modell\n8;Helios;Ventilatorbox;SB 125 A\n9;Geberit;Duofix;\n10;;Unbekannt;\n",encoding="utf-8")
            result=audit_file(inp,out)
            self.assertEqual(result["testdatensaetze"],3)
            self.assertEqual(result["hersteller_mit_nennung"],2)
            self.assertEqual(result["arge_marke_in_publizierter_liste"],1)
            self.assertEqual(result["produkt_durch_zentrale_datenquelle_live_bestaetigt"],0)
            with out.open(encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f,delimiter=";"))
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[0]["Hersteller"],"Helios")

if __name__=="__main__":
    unittest.main()
