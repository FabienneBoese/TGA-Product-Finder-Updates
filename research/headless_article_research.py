"""Headless manufacturer research against the private 59-row diagnosis dataset.

Does not assign article numbers to the project. Records evidence for review.
"""
import argparse,csv,datetime,io,json,re,sys
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from manufacturer_article_engine import source_records,pdf_records,same_host

DOMAINS={"helios":"heliosventilatoren.de","trox":"trox.de","lunos":"lunos.de","rockwool":"rockwool.com","geberit":"geberit.de","grohe":"grohe.de","viega":"viega.de","clage":"clage.de","alape":"alape.com","witingsthal":"wittingsthal.de","wittingsthal":"wittingsthal.de","danfoss":"danfoss.com","kermi":"kermi.com","grundfos":"grundfos.com","duravit":"duravit.de","laufen":"laufen.com","hewi":"hewi.de","jung":"jung-pumpen.de","viessmann":"viessmann.de","vaillant":"vaillant.de","reflex":"reflex-winkelmann.com","wika":"wika.com","imi heimeier":"imi-hydronic.com","ostendorf":"ostendorf-kunststoffe.com","kemper":"kemper-group.com","villeroy":"villeroy-boch.de","newo":"newo.de","herzbach":"herzbach.com","emco":"emco-bath.com","schedel":"schedel-bad.de"}
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; TGA-Product-Finder-Diagnosis/1.0)"}

def domain_for(maker):
 key=str(maker or "").casefold()
 return next((v for k,v in DOMAINS.items() if k in key),"")

# Document search lessons: official product URLs are stronger than generic web snippets.
# Only official domains are accepted, and codes require product-local evidence.
KNOWN_PRODUCTS={
 ("helios","sb 125 a"):"https://www.heliosventilatoren.de/de/produkte/boxventilatoren/silentbox/sb-125-a-09506",
 ("helios","pa 10"):"https://www.heliosventilatoren.de/de/produkte/messen-steuern-regeln/betriebsschalter/pa-10-01735",
 ("geberit","sigma50"):"https://catalog.geberit.de/de-DE/product/PRO_841159",
 ("trox","fk2-eu"):"https://www.trox.de/brandschutzklappen/fk2-eu-d43c8f48f846955c",
 ("trox","tve"):"https://www.trox.de/vvs-regelgeraete/tve-3fb25f4ac74c6313",
}
def seeded_urls(maker,product,model):
 text=" ".join((str(product or ""),str(model or ""))).casefold()
 return [url for (m,k),url in KNOWN_PRODUCTS.items() if m in str(maker).casefold() and k in text]

def discover(session,domain,product,model,maker=""):
 from urllib.parse import parse_qs,unquote
 urls=seeded_urls(maker,product,model)
 notes=[]
 query="site:"+domain+" "+str(product or "")+" "+str(model or "")
 # Avoid Google's 429 responses. Try two independent public discovery endpoints.
 for endpoint,param in (("https://www.bing.com/search","q"),("https://www.google.com/search","q")):
  if len(urls)>=5:break
  try:
   response=session.get(endpoint,params={param:query},headers=HEADERS,timeout=12)
   if response.status_code!=200:
    notes.append(urlparse(endpoint).hostname+" HTTP "+str(response.status_code))
    continue
   soup=BeautifulSoup(response.text,"html.parser")
   for a in soup.select("a[href]"):
    href=a.get("href","")
    if href.startswith("/url?"):href=parse_qs(urlparse(href).query).get("q",[""])[0]
    if href.startswith("https://") and same_host(href,domain) and href not in urls:
     urls.append(href)
    if len(urls)>=5:break
   if not urls:notes.append(urlparse(endpoint).hostname+" ohne Hersteller-URLs")
  except requests.RequestException as exc:
   notes.append(urlparse(endpoint).hostname+" "+type(exc).__name__)
 return urls," | ".join(notes)

def inspect(session,row):
 maker=row.get("Hersteller","")
 product=row.get("Produkt","")
 model=row.get("Typ / Modell","")
 dimension=row.get("Dimension","")
 domain=domain_for(maker)
 out=dict(row)
 out.update({"Herstellerdomain":domain,"Gefundene URLs":"","Quellen-Diagnose":"","Suchdienst-Diagnose":"","Artikelnummern-Kandidaten":"","Quellen":"","Status":""})
 if not maker.strip():out["Status"]="Hersteller fehlt";return out
 if not domain:out["Status"]="Herstellerdomain unbekannt";return out
 urls,err=discover(session,domain,product,model,maker)
 out["Gefundene URLs"]=" | ".join(urls)
 out["Suchdienst-Diagnose"]=err
 if not urls:out["Status"]="Keine Hersteller-URLs: "+err;return out
 attempts=[];hits=[]
 for url in urls:
  try:
   response=session.get(url,headers=HEADERS,timeout=12,allow_redirects=False)
   if response.status_code!=200:attempts.append(url+" HTTP "+str(response.status_code));continue
   if not same_host(response.url,domain):attempts.append(url+" Fremddomain");continue
   pdf="pdf" in response.headers.get("Content-Type","").lower() or urlparse(url).path.lower().endswith(".pdf")
   if pdf:
    attempts.append(url+" PDF gefunden; Textextraktion noch nicht aktiviert")
    continue
   records=source_records(response.text,model=model,dimension=dimension,product=product)
   # A family catalogue must not assign its unrelated variant numbers.
   if "catalog.geberit.de" in urlparse(url).hostname.lower() and not model:
    records=[]
    attempts.append(url+" Produktfamilie: Variantenauswahl erforderlich")
   attempts.append(url+(" Kandidaten: "+str(len(records)) if records else " keine belegte Artikelnummer"))
   hits.extend((code,url) for code,_ in records)
  except requests.RequestException as exc:attempts.append(url+" "+type(exc).__name__)
 out["Quellen-Diagnose"]=" | ".join(attempts)
 out["Artikelnummern-Kandidaten"]=", ".join(dict.fromkeys(c for c,_ in hits))
 out["Quellen"]=" | ".join(dict.fromkeys(u for _,u in hits))
 out["Status"]="Kandidaten – manuell prüfen" if hits else "Keine belegte Artikelnummer"
 return out

def run(input_path,output_path):
 with open(input_path,encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f,delimiter=";"))
 if not rows:raise ValueError("Keine Datensätze")
 session=requests.Session()
 result=[inspect(session,row) for row in rows]
 fields=list(dict.fromkeys(k for row in result for k in row))
 Path(output_path).parent.mkdir(parents=True,exist_ok=True)
 with open(output_path,"w",encoding="utf-8-sig",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=fields,delimiter=";");writer.writeheader();writer.writerows(result)
 print(json.dumps({"rows":len(result),"candidates":sum(bool(r["Artikelnummern-Kandidaten"]) for r in result),"with_urls":sum(bool(r["Gefundene URLs"]) for r in result),"output":str(output_path)}))
 return result

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("input");p.add_argument("output");a=p.parse_args()
 run(a.input,a.output)
