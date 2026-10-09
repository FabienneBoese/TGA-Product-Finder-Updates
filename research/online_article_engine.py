"""Herstellerübergreifende Online-Artikelrecherche; Treffer niemals automatisch bestätigen."""
import io
import re
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin, parse_qs
from bs4 import BeautifulSoup

_HEADERS={"User-Agent":"Mozilla/5.0 (compatible; TGAProductFinder/1.0)"}
_PATTERN=re.compile(r"(?:Artikel(?:nummer|[- ]?Nr\.)|Art\.-?Nr\.?|Bestell(?:nummer|[- ]?Nr\.)|Order\s*(?:No\.?|Number)|Product\s*(?:Code|No\.?))\s*[:#-]?\s*([A-Z0-9][A-Z0-9./-]{3,29})",re.I)
_BLOCK={"einbaudatum","artikelnummer","bestellnummer","datenblatt","montage","download","technische","information"}

def _tga_official(url, domain):
    u=urlparse(url)
    host=(u.hostname or "").lower()
    return u.scheme=="https" and (host==domain or host.endswith("."+domain)) and not (u.username or u.password)

def _tga_codes(text):
    out=[]
    for m in _PATTERN.finditer(text):
        val=m.group(1).strip(".,;:")
        if not any(c.isdigit() for c in val) or val.lower() in _BLOCK:continue
        if re.fullmatch(r"(?:19|20)\d{2}",val):continue
        if re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-](?:19|20)?\d{2}",val):continue
        if val not in out:out.append(val)
    return out

def _tga_source_text(response):
    ct=response.headers.get("Content-Type","").lower()
    if "pdf" in ct or response.url.lower().split("?")[0].endswith(".pdf"):
        if len(response.content)>12_000_000:return ""
        try:
            from pypdf import PdfReader
            pdf=PdfReader(io.BytesIO(response.content))
            return " ".join((p.extract_text() or "") for p in pdf.pages[:12])
        except Exception:return ""
    if "html" not in ct and "text/plain" not in ct:return ""
    if len(response.content)>3_000_000:return ""
    soup=BeautifulSoup(response.text,"html.parser")
    for t in soup(["script","style","nav","footer"]):t.decompose()
    return soup.get_text(" ",strip=True)

def _tga_discover_urls(session,query,domain,limit=6):
    urls=[]
    def add(url):
        if _tga_official(url,domain) and url not in urls:urls.append(url)
    try:
        r=session.get("https://www.bing.com/search",params={"q":query+" site:"+domain,"format":"rss"},headers=_HEADERS,timeout=8)
        r.raise_for_status()
        for item in ET.fromstring(r.content).findall(".//item"):
            add((item.findtext("link") or "").strip())
            if len(urls)>=limit:break
    except (requests.RequestException,ET.ParseError):pass
    if len(urls)<limit:
        try:
            r=session.get("https://www.google.com/search",params={"q":query+" site:"+domain},headers=_HEADERS,timeout=8)
            r.raise_for_status()
            for a in BeautifulSoup(r.text,"html.parser").find_all("a",href=True):
                u=a["href"]
                if u.startswith("/url?"):u=parse_qs(urlparse(u).query).get("q",[""])[0]
                add(u)
                if len(urls)>=limit:break
        except requests.RequestException:pass
    return urls[:limit]

def _tga_research_online(maker,product,model="",dimension="",original_code="",session=None,domain=None):
    domain=domain or _tga_maker_domain(maker) or _tga_extra_domains(maker)
    if not domain:return {"status":"Herstellerdomain unbekannt","candidates":[],"sources":[]}
    sess=session or requests.Session()
    query=" ".join(str(x or "").strip() for x in (maker,product,model,dimension,original_code)).strip()
    urls=_tga_discover_urls(sess,query,domain)
    candidates=[];sources=[]
    for url in urls:
        try:
            r=sess.get(url,headers=_HEADERS,timeout=10,allow_redirects=False)
            if r.status_code!=200:continue
            if not _tga_official(r.url,domain):continue
            txt=_tga_source_text(r)
            if not txt:continue
            sources.append(url)
            # Reject cross-product pages: model must occur on the source if supplied.
            if model and re.sub(r"\W+","",model).casefold() not in re.sub(r"\W+","",txt).casefold():
                continue
            for code in _tga_codes(txt):
                if (code,url) not in candidates:candidates.append((code,url))
        except requests.RequestException:continue
    return {"status":"Kandidaten – technische Prüfung offen" if candidates else ("Quellen ohne belegte Artikelnummer" if sources else "Keine abrufbaren Herstellerquellen"),
            "candidates":candidates[:20],"sources":sources}
