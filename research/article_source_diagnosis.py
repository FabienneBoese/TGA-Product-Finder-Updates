"""Detailed manufacturer-source diagnostics without automatic assignment."""
import requests

def _tga_diagnose_sources(maker,query,model="",dimension=""):
 domain=_tga_maker_domain(maker) or _tga_extra_domains(maker)
 out={"domain":domain,"urls":[],"attempts":[],"hits":[],"status":""}
 if not domain:
  out["status"]="Herstellerdomain unbekannt"
  return out
 client=requests.Session()
 try:urls=_tga_discover_urls(client,query,domain)
 except requests.RequestException as e:
  out["status"]="Suchdienst nicht erreichbar"
  out["attempts"].append(("Suchdienst",type(e).__name__))
  return out
 out["urls"]=urls[:10]
 for url in urls[:10]:
  try:
   r=client.get(url,headers=_HEADERS,timeout=12,allow_redirects=False)
   if r.status_code!=200:
    out["attempts"].append((url,"HTTP "+str(r.status_code)));continue
   if not same_host(r.url,domain):
    out["attempts"].append((url,"Fremddomain"));continue
   pdf="pdf" in r.headers.get("Content-Type","").lower() or r.url.lower().split("?")[0].endswith(".pdf")
   body=_tga_source_text(r) if pdf else r.text
   if not body:
    out["attempts"].append((url,"Inhalt leer"));continue
   hits=pdf_records(body,model,dimension) if pdf else source_records(body,model,dimension,query)
   out["attempts"].append((url,"Kandidat gefunden" if hits else "Keine belegte Artikelnummer"))
   for code,evidence in hits:
    if (code,url) not in out["hits"]:out["hits"].append((code,url))
  except requests.RequestException as e:
   out["attempts"].append((url,type(e).__name__))
  except (ValueError,TypeError) as e:
   out["attempts"].append((url,"Auswertung: "+type(e).__name__))
 out["status"]=("Kandidaten gefunden" if out["hits"] else "Keine Hersteller-URLs gefunden" if not urls else "Keine belegte Artikelnummer")
 return out
