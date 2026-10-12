"""Provider coverage / readiness audit for a private TGA product list.

Crucial separation: a manufacturer listed by a platform is NOT proof that a
specific product is available. No private data, credentials, or catalog contents
are manufactured from provider marketing claims.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

# Public ARGE-member brand examples named in the ARGE factsheet. Historical,
# non-exhaustive list; some more brands may be present in the 2026 portal.
# https://building-masterdata.com/wp-content/uploads/ARGE_Factsheet_More_efficient_together.pdf
ARGE_DOCUMENTED_BRANDS = frozenset({
    "airfit", "allmess", "arbonia", "bette", "biral", "koro",
    "duravit", "geberit", "grundfos", "hansgrohe", "hewi",
    "hueppe", "ibp group", "kaldewei", "kampmann", "kemper",
    "kermi", "kessel", "ksb", "kwc", "neoperl",
    "normbau", "pentair", "reflex", "remko", "roth",
    "schell", "schuetz", "tece", "viega", "wilo", "wolf",
    # ARGE's 2026 executive board explicitly names Danfoss.
    # https://www.arge.de/arge/vorstand/
    "danfoss",
})

def normalize_maker(value):
    raw = str(value or "").casefold().strip()
    replacements = {"ä":"ae","ö":"oe","ü":"ue","ß":"ss","ø":"o"}
    for a,b in replacements.items():
        raw=raw.replace(a,b)
    import re
    raw=re.sub(r"\s+", " ", raw)
    if not raw:
        return ""
    # Do not allow substring collisions across unrelated manufacturer names.
    for prefix, normalized in (
        ("herzbach /", "herzbach"), ("clage gmbh", "clage"),
        ("witingsthal", "wittigsthal"), ("wittingsthal", "wittigsthal"),
    ):
        if raw.startswith(prefix):
            return normalized
    return raw

def audit_rows(rows):
    records = []
    for item in rows:
        maker=normalize_maker(item.get("Hersteller",""))
        listed=maker in ARGE_DOCUMENTED_BRANDS
        result=dict(item)
        result.update({
            "Hersteller_normiert":maker,
            "Typ_Modell_in_Liste": "Ja" if str(item.get("Typ / Modell","")).strip() else "Nein",
            "Artikelnummer_Kandidaten_in_Liste": "Ja" if str(item.get("Artikelnummern-Kandidaten","")).strip() else "Nein",
            "ARGE_Marke_in_publizierten_Beispielen":
               ("Ja" if listed else ("Hersteller fehlt" if not maker else "Nicht im Beispielnachweis")),
            "ARGE_Produkt_nachgewiesen":"Nicht geprüft – Datenfreigabe erforderlich" if maker else "Hersteller fehlt",
            "OXOMI_Produkt_nachgewiesen":"Nicht geprüft – autorisiertes Portal erforderlich" if maker else "Hersteller fehlt",
            "Icecat_Produkt_nachgewiesen":"Nicht geprüft – Katalogzugang/Abdeckung unbekannt" if maker else "Hersteller fehlt",
            "AUSSCHREIBEN_Produkt_nachgewiesen":"Nicht geprüft – kein verifizierter Produkteintrag" if maker else "Hersteller fehlt",
            "Zentrale_Produktquelle_live_bestaetigt":"Nein",
            "Datenstatus":"Hersteller fehlt" if not maker else "Kein verifizierter Einzelartikel aus zentraler Quelle",
        })
        records.append(result)
    return records

def audit_file(source, destination):
    with Path(source).open(encoding="utf-8-sig",newline="") as stream:
        rows=list(csv.DictReader(stream,delimiter=";"))
    if not rows:
        raise ValueError("Keine Produktdatensätze")
    results=audit_rows(rows)
    path=Path(destination)
    path.parent.mkdir(parents=True,exist_ok=True)
    headers=list(dict.fromkeys(key for row in results for key in row))
    with path.open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=headers,delimiter=";")
        writer.writeheader();writer.writerows(results)
    normalized={r["Hersteller_normiert"] for r in results if r["Hersteller_normiert"]}
    arge_brands={r["Hersteller_normiert"] for r in results
                 if r["ARGE_Marke_in_publizierten_Beispielen"]=="Ja"}
    summary={
        "testdatensaetze":len(results),
        "hersteller_mit_nennung":sum(bool(r["Hersteller_normiert"]) for r in results),
        "mit_typ_modell":sum(r["Typ_Modell_in_Liste"]=="Ja" for r in results),
        "mit_artikelnummer_kandidaten":sum(r["Artikelnummer_Kandidaten_in_Liste"]=="Ja" for r in results),
        "unterschiedliche_hersteller":len(normalized),
        "arge_marke_in_publizierter_liste":sum(r["ARGE_Marke_in_publizierten_Beispielen"]=="Ja" for r in results),
        "arge_unterschiedliche_marken":len(arge_brands),
        "arge_marken":sorted(arge_brands),
        "produkt_durch_zentrale_datenquelle_live_bestaetigt":0,
        "grund":"Keine Provider-Kataloge / berechtigten Live-API-Abfragen im Test verfügbar",
        "bericht":str(path),
    }
    print(json.dumps(summary,ensure_ascii=False))
    return summary

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("target")
    args=parser.parse_args()
    audit_file(args.source,args.target)
