"""Headless manufacturer research against the private 59-row diagnosis dataset.

Does not assign article numbers to the project. Records evidence for review.
"""
import argparse,csv,datetime,io,json,re,sys
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from manufacturer_article_engine import source_records,same_host

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
 ("wika","111.10"):"https://www.wika.com/de-de/111_10_111_12.WIKA",
 ("danfoss","ecl comfort 310"):"https://designcenter.danfoss.com/products/climate-solutions-for-heating/electronic-controllers-and-monitoring-solutions/ecl-comfort-controllers/ecl-comfort-310?tab=products",
 ("jung pumpen","u3k"):"https://www.jung-pumpen.de/produkte/pumpen/u3/u3k-10-m-leitung",
 ("rockwool","conlit 150"):"https://www.rockwool.com/de/produkte/conlit-150-u/",
 ("trox","fkrs-eu"):"https://www.trox.de/brandschutzklappen/fkrs-eu-065efc2b4efeb254",
 ("trox","fk2-eu"):"https://www.trox.de/brandschutzklappen/fk2-eu-d43c8f48f846955c",
 ("trox","tve"):"https://www.trox.de/vvs-regelgeraete/tve-3fb25f4ac74c6313",
}
def seeded_urls(maker,product,model):
 text=" ".join((str(product or ""),str(model or ""))).casefold()
 return [url for (m,k),url in KNOWN_PRODUCTS.items() if m in str(maker).casefold() and k in text]

SITEMAP_CACHE={}
def sitemap_urls(session,domain,model,product=""):
 """Bounded official sitemap lookup, shared across products of one manufacturer."""
 terms=[re.sub(r"[^a-z0-9]","",t.casefold()) for t in re.findall(r"[\\w-]{3,}",str(model or "")+" "+str(product or ""))]
 terms=[t for t in terms if len(t)>=4 and t not in {"element","ventilator","produkt","pumpe","gehaeuse","gehaüse","duofix","gebe"}]
 if not terms:return []
 if domain not in SITEMAP_CACHE:
  entries=[]
  try:
   r=session.get("https://"+domain+"/sitemap.xml",headers=HEADERS,timeout=8)
   if r.status_code==200 and len(r.content)<5_000_000:
    soup=BeautifulSoup(r.content,"html.parser")
    entries=[x.get_text(strip=True) for x in soup.find_all("loc")[:12000]]
    if entries and all(x.endswith(".xml") for x in entries[:min(3,len(entries))]):
     index=entries[:4];entries=[]
     for child in index:
      if not same_host(child,domain):continue
      sub=session.get(child,headers=HEADERS,timeout=8)
      if sub.status_code==200 and len(sub.content)<5_000_000:
       entries.extend(x.get_text(strip=True) for x in BeautifulSoup(sub.content,"html.parser").find_all("loc")[:12000])
  except requests.RequestException:pass
  SITEMAP_CACHE[domain]=[u for u in entries if u.startswith("https://") and same_host(u,domain) and not u.endswith(".xml")][:25000]
 ranked=[]
 for u in SITEMAP_CACHE[domain]:
  path=re.sub(r"[^a-z0-9]","",urlparse(u).path.casefold())
  score=sum(len(t) for t in terms if t in path)
  if score>=4:ranked.append((score,u))
 return [u for _,u in sorted(ranked,key=lambda x:-x[0])[:5]]


# Product-page discovery is independent from article-number and document extraction.
# All candidate URLs must belong to the manufacturer's official domain.
def search_terms(product,model):
 stop={"und","fuer","für","mit","ohne","alle","element","artikel","produkt","chrom","weiss","weiß","gewerbe","hersteller","bad","ein","eine","von","die","der","das","den","bei","auf","mm","dn"}
 tokens=re.findall(r"[a-z0-9]+",str(model or "").casefold().replace("ß","ss"))
 tokens += re.findall(r"[a-z0-9]+",str(product or "").casefold().replace("ß","ss"))
 return list(dict.fromkeys(t for t in tokens if len(t)>=3 and t not in stop))[:12]

def product_page_score(url,title,product,model):
 """Evidence-weighted match; never count a manufacturer home page as a product page."""
 from urllib.parse import unquote
 path=unquote(urlparse(url).path).casefold()
 title=str(title or "").casefold()
 if path in ("","/","/de","/de-de","/de/") or path.endswith((".pdf",".xml")):return 0
 model_tokens=search_terms("",model)
 product_tokens=search_terms(product,"")
 path_flat=re.sub(r"[^a-z0-9]","",path)
 title_flat=re.sub(r"[^a-z0-9]","",title)
 model_matches=sum(len(t) for t in model_tokens if t in path_flat or t in title_flat)
 product_matches=sum(len(t) for t in product_tokens if t in path_flat or t in title_flat)
 if model_tokens and not model_matches:return 0
 distinctive=[t for t in model_tokens if len(t)>=4 and not t.isdigit()]
 if distinctive and not any(t in path_flat or t in title_flat for t in distinctive):return 0
 if not model_tokens and not product_matches:return 0
 score=3*model_matches+product_matches
 if any(x in path for x in ("/produkt","/product","/artikel","/catalog","/katalog","/brandschutzklappen","/series/")):score+=6
 return score

NAVIGATION_CACHE={}
def internal_product_links(session,domain,product,model):
 """Discover official catalog/category links without relying on search-engine results."""
 roots=["https://"+domain+"/","https://www."+domain+"/"]
 if domain=="geberit.de":roots=["https://catalog.geberit.de/de-DE","https://www.geberit.de/"]
 elif domain=="trox.de":roots=["https://www.trox.de/brand--und-rauchschutzsysteme/brandschutzklappen-9abc97fe0357ecd2","https://www.trox.de/"]
 seen=set();ranked=[]
 if domain in NAVIGATION_CACHE:
  candidates=NAVIGATION_CACHE[domain]
 else:
  candidates=[]
  for root in roots:
   try:
    response=session.get(root,headers=HEADERS,timeout=8)
    if response.status_code!=200 or not same_host(response.url,domain):continue
    soup=BeautifulSoup(response.text,"html.parser")
    for a in soup.select("a[href]")[:2000]:
     from urllib.parse import urljoin
     url=urljoin(response.url,a.get("href",""))
     if not url.startswith("https://") or not same_host(url,domain):continue
     if url in seen:continue
     seen.add(url)
     candidates.append((url,a.get_text(" ",strip=True)))
   except requests.RequestException:continue
  NAVIGATION_CACHE[domain]=candidates
 for url,title in candidates:
  score=product_page_score(url,title,product,model)
  if score:ranked.append((score,url))
 return [url for _,url in sorted(ranked,key=lambda x:-x[0])[:5]]

DISABLED_SEARCH_PROVIDERS=set()
def discover(session,domain,product,model,maker=""):
 from urllib.parse import parse_qs,unquote
 urls=seeded_urls(maker,product,model)
 for candidate in internal_product_links(session,domain,product,model):
  if candidate not in urls:urls.append(candidate)
 for candidate in sitemap_urls(session,domain,model,product):
  if candidate not in urls:urls.append(candidate)
 notes=[]
 query="site:"+domain+" "+str(product or "")+" "+str(model or "")
 # Avoid Google's 429 responses. Try two independent public discovery endpoints.
 for endpoint,param in (("https://www.bing.com/search?format=rss","q"),("https://www.bing.com/search","q")):
  if len(urls)>=5:break
  if endpoint in DISABLED_SEARCH_PROVIDERS:continue
  try:
   response=session.get(endpoint,params={param:query},headers=HEADERS,timeout=12)
   if response.status_code!=200:
    if response.status_code in (403,429):DISABLED_SEARCH_PROVIDERS.add(endpoint)
    notes.append(urlparse(endpoint).hostname+" HTTP "+str(response.status_code))
    continue
   soup=BeautifulSoup(response.text,"html.parser")
   for item in soup.select("item"):
    link=item.find("link")
    if link:
     href=link.get_text(strip=True)
     if href.startswith("https://") and same_host(href,domain) and href not in urls:urls.append(href)
   for a in soup.select("a[href]"):
    href=a.get("href","")
    if href.startswith("/url?"):href=parse_qs(urlparse(href).query).get("q",[""])[0]
    if href.startswith("/l/?"):href=parse_qs(urlparse(href).query).get("uddg",[""])[0]
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
 out.update({"Herstellerdomain":domain,"Gefundene URLs":"","Quellen-Diagnose":"","Suchdienst-Diagnose":"","Artikelnummern-Kandidaten":"","Quellen":"","Status":"","Produktseiten-Status":"","Produktseiten-URL":""})
 if not str(maker or "").strip():out["Status"]="Hersteller fehlt";return out
 if not domain:out["Status"]="Herstellerdomain unbekannt";return out
 urls,err=discover(session,domain,product,model,maker)
 out["Gefundene URLs"]=" | ".join(urls)
 out["Suchdienst-Diagnose"]=err
 if not urls:
  out["Produktseiten-Status"]="Keine Produktseite gefunden"
  out["Status"]="Keine Hersteller-Produktseite: "+err
  return out
 attempts=[];hits=[];verified_pages=[]
 for url in urls:
  try:
   response=session.get(url,headers=HEADERS,timeout=12,allow_redirects=False)
   if response.status_code!=200:attempts.append(url+" HTTP "+str(response.status_code));continue
   if not same_host(response.url,domain):attempts.append(url+" Fremddomain");continue
   pdf="pdf" in response.headers.get("Content-Type","").lower() or urlparse(url).path.lower().endswith(".pdf")
   if pdf:
    attempts.append(url+" PDF nicht für Artikelnummernsuche verwendet")
    continue
   soup=BeautifulSoup(response.text,"html.parser")
   heading=" ".join(x.get_text(" ",strip=True) for x in soup.select("h1")[:2])
   title=(soup.title.get_text(" ",strip=True) if soup.title else "")+" "+heading
   score=product_page_score(response.url,title,product,model)
   if score>=12:verified_pages.append((score,response.url))
   records=source_records(response.text,model=model,dimension=dimension,product=product)
   # A family catalogue must not assign its unrelated variant numbers.
   if "catalog.geberit.de" in urlparse(url).hostname.lower() and not re.fullmatch(r"[0-9]{3}\\.[0-9A-Z]{3}\\.[0-9A-Z]{2}\\.[0-9A-Z]",str(model or "")):
    records=[]
    attempts.append(url+" Produktfamilie: Variantenauswahl erforderlich; keine Einzelartikel-Übernahme")
   attempts.append(url+(" Kandidaten: "+str(len(records)) if records else " keine belegte Artikelnummer"))
   hits.extend((code,url) for code,_ in records)
  except requests.RequestException as exc:attempts.append(url+" "+type(exc).__name__)
 out["Quellen-Diagnose"]=" | ".join(attempts)
 if verified_pages:
  out["Produktseiten-URL"]=max(verified_pages)[1]
  out["Produktseiten-Status"]="Passende Hersteller-Produktseite (automatisch bewertet)"
 else:out["Produktseiten-Status"]="Nur unbestätigte Links oder Produktfamilie"
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
