"""Universelle, quellengestützte Produktsuche für TGA-Produktlisten.

Herstellerübergreifender Suchkern – keine herstellerspezifischen Produktregeln.
Die Bausteine unterscheiden Produktfamilie, Modell/Typ, bestätigte Einzelartikel
und echte Artikelnummern. Reine Indexbelege dürfen keine Artikelnummern
generieren oder einen überprüften Einzelartikel vortäuschen.

Datenquellen:
- öffentliche RSS-Suchindizes (Best-Effort, kein SLA),
- später lizenzierte API-Adapter, die dieselbe SearchHit-Schnittstelle nutzen,
- optional nachgelagerte Prüfung erlaubter offizieller Produktseiten.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

STOP = frozenset("""der die das den dem des und oder fuer fur mit ohne einer einem eines
eine einer eines alle artikel produkt produkte fuer entsprechend gem technik
sonder gegen baustelle inklusive inkl von fuer zur zum am im in auf ein
weiss weiß chrom verchromt matt standard neu bad mm dn cm m l
element fuer gehause gehäuse badaccessoires bedarfsposition ohne gb
""".split())
VERY_GENERIC = frozenset(("wc","waschtisch","handwaschbecken","badewanne",
                         "geruchsverschluss","systemtrenner","kugelhahn",
                         "heizungs-kugelhahn","dusche","pumpe","manometer"))
# Official alternate hostnames were independently verified by our
# manufacturer website research. Never treat any arbitrary redirect as official.
ALIASES = {
    "wika.com": ("wika.com", "wika.de"),
    "villeroy-boch.de": ("villeroy-boch.de", "villeroy-boch.com"),
    "imi-hydronic.com": ("imi-hydronic.com", "imiplc.com"),
    "alape.com": ("alape.com", "laufen.com"),
    "viega.de": ("viega.de", "viega.com"),
    "geberit.de": ("geberit.de", "geberit.com"),
    "duravit.de": ("duravit.de", "duravit.com"),
    "clage.de": ("clage.de", "clage.com"),
    "hewi.de": ("hewi.de", "hewi.com"),
    "kermi.com": ("kermi.com", "kermi.de"),
    "emco-bath.com": ("emco-bath.com", "emco-world.com"),
    "newo.de": ("newo.de", "newo.at"),
    "schedel-bad.de": ("schedel-bad.de", "schedel-badinnovation.de"),
}
KNOWN_DOMAINS = {
    "helios":"heliosventilatoren.de", "trox":"trox.de",
    "lunos":"lunos.de", "danfoss":"danfoss.com",
    "reflex":"reflex-winkelmann.com","wika":"wika.com",
    "viega":"viega.de","imi heimeier":"imi-hydronic.com",
    "rockwool":"rockwool.com","kermi":"kermi.com",
    "ostendorf":"ostendorf-kunststoffe.com","jung pumpen":"jung-pumpen.de",
    "kemper":"kemper-group.com","geberit":"geberit.de",
    "villeroy & boch":"villeroy-boch.de", "newo":"newo.de",
    "duravit":"duravit.de","herzbach":"herzbach.com",
    "emco":"emco-bath.com","schedel multistar":"schedel-bad.de",
    "laufen":"laufen.com","hewi":"hewi.de",
    "alape":"alape.com","witingsthal":"wittigsthal.de",
    "wittigsthal":"wittigsthal.de", "clage gmbh":"clage.de",
}
INDEX_PARTNERS = ("ausschreiben.de", "oxomi.com", "icecat.biz",
                  "building-masterdata.com")
INDEX_HEADERS = {"User-Agent":"TGA-Product-Finder/2.4 (public index research)"}


def normalize(text):
    text = str(text or "").replace("ß","ss").replace("ẞ","ss")
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in text if not unicodedata.combining(char))


def compact(text):
    return re.sub("[^a-z0-9]","",normalize(text))


def tokens(text):
    return [x for x in re.findall("[a-z0-9]+",normalize(text))
            if x not in STOP and len(x)>=2]


def valid_https(url):
    try:
        parsed = urlparse(url)
        return (parsed.scheme=="https" and bool(parsed.hostname)
                and not (parsed.username or parsed.password)
                and parsed.hostname not in ("localhost","127.0.0.1"))
    except ValueError:
        return False


def allowed_host(url, official_roots):
    if not valid_https(url):
        return False
    host=urlparse(url).hostname.lower()
    return any(host==x or host.endswith("."+x) for x in official_roots)


def maker_domain(maker):
    return KNOWN_DOMAINS.get(normalize(maker).strip(),"")


def maker_aliases(maker):
    domain=maker_domain(maker)
    return ALIASES.get(domain,(domain,)) if domain else ()


def model_search_key(model):
    """A model is a type, NOT necessarily a manufacturer article number."""
    value=str(model or "").strip()
    if not value:
        return ""
    # Slash-separated type families include variants, but preserve full model
    # in the report. Search engines benefit from an initial family term.
    initial=value.split("/")[0].strip()
    if len(initial)>=3 and any(ch.isalpha() for ch in initial):
        return initial
    return value


def useful_product_tokens(description, maker):
    maker_words=set(tokens(maker))
    return [t for t in tokens(description) if t not in maker_words]


def query_for(row):
    maker=str(row.get("Hersteller","")).strip()
    name=str(row.get("Produkt","")).strip()
    model=str(row.get("Typ / Modell","")).strip()
    if not maker:
        return ""
    key=model_search_key(model)
    if key:
        return " ".join([maker,'"'+key+'"',name[:65]]).strip()
    important=useful_product_tokens(name,maker)
    if not important:
        return maker
    return " ".join([maker]+important[:8])


def family_class(row):
    maker=str(row.get("Hersteller","")).strip()
    name=str(row.get("Produkt","")).strip()
    model=str(row.get("Typ / Modell","")).strip()
    product=compact(name)
    if not maker:
        return "Hersteller fehlt"
    if "bedarfsposition" in normalize(name):
        return "Bedarfsposition – gesondert prüfen"
    if compact(model) in ("mapresstherm","eurosmartce") and model:
        return "Produktfamilie – Auswahl erforderlich"
    if model:
        return "Typ/Modell angegeben – Artikelnummer unbelegt"
    phrase=tokens(name)
    if len(phrase)>=3 and (len(phrase)>4 or any(
        len(x)>=6 for x in phrase
    )):
        return "Produktbeschreibung – Variante offen"
    if product in {compact(x) for x in VERY_GENERIC} or len(phrase)<=2:
        return "Produktfamilie / unspezifische Bezeichnung"
    return "Produktbeschreibung – Variante offen"


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str = ""
    provider: str = "suchindex"


@dataclass(frozen=True)
class RankedHit:
    title: str
    url: str
    provider: str
    score: int
    evidence: str
    source_kind: str


class BingRSS:
    name="bing_rss"
    def __init__(self, session=None):
        self.session=session or requests.Session()
        self.last_error=""
    def search(self, query, limit=12):
        if not query or len(query)>400:
            return []
        try:
            response=self.session.get(
                "https://www.bing.com/search",
                params={"q":query,"format":"rss","setlang":"de-DE"},
                headers=INDEX_HEADERS,timeout=(5,12))
            if response.status_code!=200:
                self.last_error="HTTP "+str(response.status_code)
                return []
            if len(response.content)>1_500_000:
                self.last_error="Antwort zu groß"
                return []
            # RSS might be replaced by a challenge / generic HTML page.
            root=ET.fromstring(response.content)
            if root.tag.lower()!="rss":
                self.last_error="Keine RSS-Antwort"
                return []
            hits=[]
            for item in root.findall(".//item"):
                url=(item.findtext("link") or "").strip()
                if not valid_https(url):
                    continue
                hits.append(SearchHit((item.findtext("title") or "").strip(),
                                      url,(item.findtext("description") or "").strip(),
                                      self.name))
                if len(hits)>=limit:
                    break
            self.last_error="" if hits else "RSS ohne gültige Treffer"
            return hits
        except (requests.RequestException,ET.ParseError,UnicodeError,ValueError) as exc:
            self.last_error=type(exc).__name__
            return []


class BraveAPI:
    """Optional paid/approved index. Credentials remain environment-only."""
    name="brave_api"
    def __init__(self, api_key, session=None):
        self.api_key=str(api_key or "").strip()
        self.session=session or requests.Session()
        self.last_error=""
    def search(self, query, limit=12):
        if not self.api_key:
            self.last_error="Kein API-Schlüssel"
            return []
        try:
            response=self.session.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q":query,"count":min(max(1,limit),20),
                        "country":"DE","search_lang":"de"},
                headers={"Accept":"application/json",
                         "X-Subscription-Token":self.api_key}, timeout=(5,12))
            if response.status_code!=200:
                self.last_error="HTTP "+str(response.status_code)
                return []
            result=response.json()
            hits=[]
            for item in result.get("web",{}).get("results",[]):
                url=item.get("url","")
                if valid_https(url):
                    hits.append(SearchHit(str(item.get("title","")),url,
                                          str(item.get("description","")),
                                          self.name))
            self.last_error=""
            return hits[:limit]
        except (requests.RequestException,ValueError,TypeError,AttributeError) as exc:
            self.last_error=type(exc).__name__
            return []


def _match(model, string):
    """Whole-model normalization, prevents misleading matches on 125 or 10."""
    normalized=compact(model)
    return bool(len(normalized)>=3 and normalized in compact(string))


def rank_hit(row,hit):
    maker=str(row.get("Hersteller","")).strip()
    product=str(row.get("Produkt","")).strip()
    model=str(row.get("Typ / Modell","")).strip()
    roots=maker_aliases(maker)
    if not roots or not valid_https(hit.url):
        return None
    parsed=urlparse(hit.url)
    path=unquote(parsed.path).lower()
    if path in ("","/","/de","/de-de","/de/","/de-de/"):
        return None
    if path.endswith((".pdf",".xml",".jpg",".png",".zip")):
        return None
    if "/search" in path or "/suche" in path:
        return None
    host=parsed.hostname.lower()
    official=allowed_host(hit.url,roots)
    partner=any(host==root or host.endswith("."+root)
                for root in INDEX_PARTNERS)
    if not official and not partner:
        return None

    # Search-engine snippets are third-party metadata, not an article proof.
    title_path=hit.title+" "+unquote(parsed.path)
    searchable=title_path+" "+hit.snippet
    key=model_search_key(model)
    whole_model=_match(model,title_path)
    family_model=_match(key,title_path)
    snippet_model=_match(model,searchable)
    prod_words=useful_product_tokens(product,maker)
    # Ignore meaningless generic word overlaps, and require actual product
    # evidence; a matching maker name or root domain alone is insufficient.
    distinctive=[x for x in prod_words if len(x)>=4 and not x.isdigit()]
    product_matches=[x for x in distinctive if x in normalize(searchable)]
    evidence=[]
    score=20 if official else 6
    if model:
        if not (whole_model or family_model or snippet_model):
            return None
        if whole_model:
            score+=50; evidence.append("Vollständiger Typ im Titel/URL")
        elif family_model:
            score+=30; evidence.append("Typfamilie im Titel/URL; Ausführung offen")
        else:
            score+=12; evidence.append("Typ nur im Indextext")
    else:
        if not distinctive or not product_matches:
            return None
        # With no model, require two independent distinctive words unless
        # a single long compound word makes the product more specific.
        if len(set(product_matches))<2:
            return None
        evidence.append("Produktbeschreibung im Index")
        score+=min(24,8*len(set(product_matches)))
    if product_matches:
        score+=min(16,4*len(set(product_matches)))
    if any(x in path for x in ("/product","/produkt","/catalog",
                                "/katalog","/artikel","/brandschutz",
                                "/produkte")):
        score+=5
    if official:
        evidence.append("Offizielle Herstellerdomain (Domainzuordnung)")
    else:
        evidence.append("Drittanbieter-Index (kein Herstellerbeleg)")
    if not (whole_model or family_model):
        score=min(score,69)
    return RankedHit(hit.title,hit.url,hit.provider,
                     min(score,99),"; ".join(evidence),
                     "Herstellerdomain" if official else "Zentrales Verzeichnis")


def find_candidates(row,providers,per_provider=12):
    query=query_for(row)
    kind=family_class(row)
    diag=[]
    if not query or "Bedarfsposition" in kind:
        return {"Suchbegriff":query,"Produktstatus":kind,
                "Trefferstatus":"Nicht recherchierbar" if not query else "Bedarfsposition",
                "Trefferzahl":0,"Bester_Treffer":"","Treffer_Quellen":"",
                "Treffer_Bewertung":"","Belege":"","Artikelnummer_automatisch":"",
                "Suchdiagnose":"Hersteller fehlt" if not query else "Bedarfsposition",
                "Kandidaten_JSON":"[]"}
    found={}
    for provider in providers:
        try:
            hits=(provider.search_for(row,limit=per_provider)
                  if hasattr(provider,"search_for")
                  else provider.search(query,limit=per_provider))
            diag.append(provider.name+": "+str(len(hits))+" Indextreffer"
                        +(("; "+provider.last_error) if getattr(provider,"last_error","") else ""))
            for hit in hits:
                scored=rank_hit(row,hit)
                if scored is None:
                    continue
                prev=found.get(scored.url)
                if prev is None or scored.score>prev.score:
                    found[scored.url]=scored
        except Exception as exc:
            diag.append(provider.name+": "+type(exc).__name__)
    ranking=sorted(found.values(),key=lambda h:(-h.score,h.url))
    best=ranking[0] if ranking else None
    state=("Offizieller Sitemap-Eintrag – Produktseite ungeprüft"
           if best and best.provider=="official_sitemap"
           else "Indexkandidat – Herstellerseite ungeprüft"
           if best and best.source_kind=="Herstellerdomain"
           else "Indexkandidat – Drittanbieter, Prüfung offen" if best
           else "Kein belastbarer Indextreffer")
    if best and best.score<55:
        state="Schwacher Indexkandidat – manuelle Prüfung erforderlich"
    return {"Suchbegriff":query,"Produktstatus":kind,
            "Trefferstatus":state,
            "Trefferzahl":len(ranking),
            "Bester_Treffer":best.url if best else "",
            "Treffer_Quellen":" | ".join(dict.fromkeys(x.provider for x in ranking[:5])),
            "Treffer_Bewertung":str(best.score) if best else "",
            "Belege":best.evidence if best else "",
            "Artikelnummer_automatisch":"",
            "Suchdiagnose":" | ".join(diag),
            "Kandidaten_JSON":json.dumps([asdict(x) for x in ranking[:5]],
                                         ensure_ascii=False)}


def process_file(source,target,provider="auto",max_rows=0,delay=0.25):
    with Path(source).open(encoding="utf-8-sig",newline="") as file:
        rows=list(csv.DictReader(file,delimiter=";"))
    if max_rows>0:
        rows=rows[:max_rows]
    if not rows:
        raise ValueError("Keine Eingabezeilen")
    if provider in ("sitemap","auto"):
        from manufacturer_sitemap_provider import OfficialSitemap
        providers=[OfficialSitemap()]
        if provider=="auto":
            apikey=os.environ.get("TGA_BRAVE_API_KEY","")
            providers.append(BraveAPI(apikey) if apikey else BingRSS())
    elif provider=="brave":
        apikey=os.environ.get("TGA_BRAVE_API_KEY","")
        if not apikey:
            raise ValueError("TGA_BRAVE_API_KEY fehlt – keine verdeckte Fallback-Suche")
        providers=[BraveAPI(apikey)]
    elif provider=="bing":
        providers=[BingRSS()]
    elif provider=="offline":
        providers=[]
    else:
        raise ValueError("Unbekannter Provider")
    outputs=[]
    for i,row in enumerate(rows):
        result=find_candidates(row,providers)
        outputs.append({**row,**result})
        if i % 10 == 0:
            print("FORTSCHRITT",i+1,"/",len(rows),row.get("Hersteller",""),
                  result["Trefferstatus"],flush=True)
        if delay and providers and i<len(rows)-1:
            time.sleep(delay)
    dest=Path(target);dest.parent.mkdir(parents=True,exist_ok=True)
    cols=list(dict.fromkeys(k for x in outputs for k in x))
    with dest.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=cols,delimiter=";")
        writer.writeheader();writer.writerows(outputs)
    counts=Counter(x["Trefferstatus"] for x in outputs)
    metrics={"datensaetze":len(outputs),
             "hersteller":len({normalize(x.get("Hersteller","")).strip() for x in rows
                               if x.get("Hersteller","").strip()}),
             "indexkandidaten":sum(bool(x["Bester_Treffer"]) for x in outputs),
             "verifizierte_einzelartikel":0,
             "automatisch_belegte_artikelnummern":0,
             "datenanbieter_live_abfragen":0,
             "status":dict(counts),"provider":provider,
             "ausgabe":str(dest)}
    print("ERGEBNIS",json.dumps(metrics,ensure_ascii=False),flush=True)
    return metrics


def main():
    p=argparse.ArgumentParser()
    p.add_argument("input");p.add_argument("output")
    p.add_argument("--provider",choices=("auto","sitemap","bing","brave","offline"),default="auto")
    p.add_argument("--max-rows",type=int,default=0)
    p.add_argument("--delay",type=float,default=0.25)
    opts=p.parse_args()
    process_file(opts.input,opts.output,opts.provider,opts.max_rows,opts.delay)


if __name__=="__main__":
    main()
