"""Diagnostics of index queries for specific known TGA example products.

Only prints public search-index metadata, never private component files.
"""
from universal_product_search import BingRSS, SearchHit, rank_hit, query_for, maker_aliases

cases=[
 ("Helios","Helios Ventilatorbox","SB 125 A","heliosventilatoren.de"),
 ("TROX","Brandschutzklappe","FKRS-EU/DE/125/Z00","trox.de"),
 ("WIKA","Manometer","111.10 NG 63","wika.com"),
 ("Geberit","BetPl. Sigma50, für 2-Mengen-Sp., Chrom gebürstet","SIGMA50","geberit.de"),
 ("CLAGE GmbH","Clage MCX3 3,5 kW 230 V","MCX3","clage.de")
]
search=BingRSS()
for maker,product,model,host in cases:
 row={"Hersteller":maker,"Produkt":product,"Typ / Modell":model}
 for phrase in [query_for(row),f"site:{host} {model.split('/')[0]}",
                f'"{maker}" "{model.split("/")[0]}"']:
  print("QUERY",repr(phrase),flush=True)
  hits=search.search(phrase,10)
  print("RSS",len(hits),search.last_error,flush=True)
  for hit in hits[:8]:
   outcome=rank_hit(row,hit)
   print("ITEM",repr(hit.title[:100]),repr(hit.url[:140]),
         "SCORE",outcome.score if outcome else "-",flush=True)
