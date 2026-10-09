"""Conservative article identity extraction from local product records.

Never treat a number on a multi-product catalog page as proof of a particular variant.
"""
import json
import re
from bs4 import BeautifulSoup

CODE_RE = re.compile(r"(?:Artikel(?:nummer|[- ]?Nr\.)|Art\.-?Nr\.?|Bestell(?:nummer|[- ]?Nr\.)|Order\s*(?:No\.?|Number)|Product\s*(?:Code|No\.?))\s*[:#-]?\s*([A-Z0-9][A-Z0-9./-]{3,29})", re.I)
BAD = {"einbaudatum", "datenblatt", "montage", "download", "artikelnummer", "bestellnummer"}
def norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

def codes(text):
    found = []
    for match in CODE_RE.finditer(str(text or "")):
        code = match.group(1).strip(".,;:")
        if (any(ch.isdigit() for ch in code) and code.casefold() not in BAD
            and not re.fullmatch(r"(?:19|20)\d\d", code)
            and not re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-](?:19|20)?\d{2}", code)
            and code not in found):
            found.append(code)
    return found

def matching_record(text, model="", dimension="", execution=""):
    compact = norm(text)
    return all(norm(v) in compact for v in (model, dimension, execution) if norm(v))

def extract_html_records(html, model="", dimension="", execution=""):
    """Return (code, evidence) only when the number belongs to a bounded record.

    HTML tables are evaluated row by row, structured Product JSON-LD object by
    object. A page-wide model mention is intentionally insufficient.
    """
    soup = BeautifulSoup(html, "html.parser")
    out = []
    def add(code, evidence):
        if code and (code, evidence) not in out:
            out.append((code, evidence))
    for row in soup.select("tr"):
        text = row.get_text(" ", strip=True)
        if matching_record(text, model, dimension, execution):
            for code in codes(text):
                add(code, "table-row")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        def walk(node):
            if isinstance(node, list):
                for child in node: walk(child)
            elif isinstance(node, dict):
                kinds = node.get("@type", [])
                kinds = [kinds] if isinstance(kinds, str) else kinds
                if "Product" in kinds:
                    fields = " ".join(str(node.get(k, "")) for k in ("name", "model", "description", "size", "color"))
                    if matching_record(fields, model, dimension, execution):
                        for key in ("sku", "mpn"):
                            val = str(node.get(key, "")).strip()
                            if val and any(c.isdigit() for c in val):
                                add(val, "product-jsonld")
                for child in node.values():
                    if isinstance(child, (list, dict)): walk(child)
        walk(payload)
    return out

def classify(records):
    """Multiple distinct codes are ambiguous, never automatically confirmed."""
    unique = sorted({code for code, _ in records})
    if not unique: return "nicht gefunden"
    if len(unique) > 1: return "mehrdeutig"
    return "Kandidat – Herstellerprüfung offen"

def extract_pdf_records(text, model="", dimension="", execution=""):
    """Extract codes only from the same PDF line or adjacent short record."""
    lines=[re.sub(r"\\s+", " ", line).strip() for line in str(text or "").splitlines()]
    result=[]
    for i,line in enumerate(lines):
        if not line: continue
        # Avoid scanning entire catalogue pages; a record is at most two lines.
        record=" ".join(lines[max(0,i-1):i+1])
        if not matching_record(record, model, dimension, execution): continue
        for code in codes(line):
            pair=(code,"pdf-line")
            if pair not in result:result.append(pair)
    return result

def extract_html_links(html, base_url, domain, limit=12):
    """Follow only same-manufacturer PDF files linked from product pages."""
    from urllib.parse import urljoin, urlparse
    soup=BeautifulSoup(html,"html.parser")
    urls=[]
    for anchor in soup.select("a[href]"):
        url=urljoin(base_url,anchor.get("href",""))
        parsed=urlparse(url)
        host=(parsed.hostname or "").lower()
        if parsed.scheme!="https" or not (host==domain or host.endswith("."+domain)):continue
        if not parsed.path.lower().endswith(".pdf"):continue
        if url not in urls:urls.append(url)
        if len(urls)>=limit:break
    return urls

def unique_single_article(records, model="", dimension=""):
    """Return a candidate only with model evidence and exactly one distinct code."""
    if not norm(model):return None
    distinct=sorted({code for code, evidence in records if evidence in ("table-row","product-jsonld","pdf-line")})
    return distinct[0] if len(distinct)==1 else None

def product_scope(model="", dimension="", description=""):
    """Defer broad product families and unspecified variants."""
    model=str(model or "").strip()
    if not model:return "zurückgestellt – Typ fehlt"
    broad=("mapress therm","eurosmart ce")
    if any(norm(x)==norm(model) for x in broad):
        return "zurückgestellt – Produktfamilie"
    return "Einzelprodukt – Recherche"
