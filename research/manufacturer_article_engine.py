"""Source-first manufacturer article research. No unverified auto assignment."""
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

LABEL=re.compile(r"(?:artikel(?:nummer|[- ]?nr\\.?|[- ]?no\\.?)|art\\.-?nr\\.?|bestell(?:nummer|[- ]?nr\\.?)|ref\\.-?no\\.?|sku|mpn)",re.I)
VALID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9./-]{3,28}$")
def compact(x):return re.sub(r"[^a-z0-9]","",str(x or "").casefold())
def valid(x):
 x=str(x or "").strip().strip(":;,")
 return bool(VALID.fullmatch(x) and any(c.isdigit() for c in x) and not re.fullmatch(r"(?:19|20)\\d{2}",x))
def same_host(url,domain):
 h=(urlparse(url).hostname or "").lower()
 return h==domain or h.endswith("."+domain)
def code_from_label(text):
 text=re.sub(r"\\s+"," ",text).strip()
 m=re.search(r"(?:Artikel(?:nummer|[- ]?Nr\\.?)|Art\\.-?Nr\\.?|Bestell(?:nummer|[- ]?Nr\\.?)|Ref\\.-?No\\.?|SKU|MPN)\\s*[:#-]?\\s*([A-Z0-9][A-Z0-9./-]{3,28})",text,re.I)
 return m.group(1) if m and valid(m.group(1)) else None
def source_records(html,model="",dimension="",product=""):
 """Bounded rows, detail-page label/value pairs, and structured Product objects."""
 import json
 soup=BeautifulSoup(html,"html.parser")
 result=[]
 def add(c,why):
  if valid(c) and (c,why) not in result:result.append((c,why))
 for tr in soup.select("tr"):
  cells=[c.get_text(" ",strip=True) for c in tr.find_all(["td","th"],recursive=False)]
  if not cells:continue
  joined=" ".join(cells)
  if model and compact(model) not in compact(joined):continue
  if dimension and compact(dimension) not in compact(joined):continue
  c=code_from_label(joined)
  if c:add(c,"Tabellenzeile")
  # Article number may precede the model, as on Helios catalogue tables.
  for idx,cell in enumerate(cells):
   if idx==0 and valid(cell) and cell!=model and compact(cell)!=compact(dimension) and len(cells)>1 and model:
    add(cell,"Produktzeile")
 # Detail page: label/value rows, but only if title matches model.
 title=" ".join(t.get_text(" ",strip=True) for t in soup.select("h1")[:2])
 if model and compact(model) in compact(title):
  for tr in soup.select("tr"):
   cells=[c.get_text(" ",strip=True) for c in tr.find_all(["th","td"],recursive=False)]
   if len(cells)>=2 and LABEL.search(cells[0]) and valid(cells[1]):add(cells[1],"Produktdetail")
  for tag in soup.select("dt"):
   if LABEL.search(tag.get_text(" ",strip=True)):
    dd=tag.find_next_sibling("dd")
    if dd and valid(dd.get_text(" ",strip=True)):add(dd.get_text(" ",strip=True),"Produktdetail")
  for text in soup.stripped_strings:
   if LABEL.search(text):
    c=code_from_label(text)
    if c:add(c,"Produktdetail")
 for script in soup.select('script[type="application/ld+json"]'):
  try:payload=json.loads(script.string or script.get_text())
  except (ValueError,TypeError):continue
  def walk(obj):
   if isinstance(obj,list):
    for item in obj:walk(item)
   elif isinstance(obj,dict):
    kind=obj.get("@type",[])
    if isinstance(kind,str):kind=[kind]
    if "Product" in kind:
     ident=" ".join(str(obj.get(k,"")) for k in ("name","model","description","size"))
     if (not model or compact(model) in compact(ident)) and (not dimension or compact(dimension) in compact(ident)):
      for k in ("sku","mpn"):
       if valid(obj.get(k)):add(str(obj[k]),"Produktdaten")
    for v in obj.values():
     if isinstance(v,(list,dict)):walk(v)
  walk(payload)
 return result
def pdf_records(text,model="",dimension=""):
 """Only bounded PDF rows; never numbers from unrelated catalogue sections."""
 out=[]
 lines=[re.sub(r"\\s+"," ",x).strip() for x in str(text or "").splitlines()]
 for i,line in enumerate(lines):
  if not line:continue
  if model and compact(model) not in compact(line):continue
  if dimension and compact(dimension) not in compact(line):continue
  c=code_from_label(line)
  if c:out.append((c,"PDF-Zeile"))
  # Common manufacturer catalogue pattern: model followed by order number.
  if model:
   m=re.search(re.escape(model)+r"\\s+([A-Z0-9][A-Z0-9./-]{3,28})\\b",line,re.I)
   if m and valid(m.group(1)):out.append((m.group(1),"PDF-Katalogzeile"))
 return list(dict.fromkeys(out))
def classify_hits(hits):
 codes=sorted(set(c for c,u in hits))
 if len(codes)>1:return "Mehrere mögliche Artikelnummern – Auswahl erforderlich"
 if len(codes)==1:return "Ein Artikelnummer-Kandidat – Herstellerquelle prüfen"
 return "Keine belegte Artikelnummer gefunden"
