"""Independent, conservative HTTP/HTML verification of official product leads.

Do not interpret a sitemap listing or an HTTP 200 alone as a verified product.
Only manufacturer-owned allowlisted hosts are fetched; an off-domain redirect
is never followed. No catalog SKU is invented from model/type strings.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

from universal_product_search import (
    allowed_host, compact, maker_aliases, model_search_key, normalize,
    useful_product_tokens,
)

BOT_MARKERS=("just a moment", "cf-chl", "checking your browser",
             "verify you are human", "attention required! | cloudflare")
HEADERS={"User-Agent":"TGA-Product-Finder/2.4 (+product evidence verification)"}


class Headings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active=[]
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("title","h1","h2"):
            self.active.append(tag)
        if tag=="meta":
            meta=dict(attrs)
            if meta.get("property") in ("og:title","twitter:title"):
                self.parts.append(meta.get("content",""))
    def handle_endtag(self,tag):
        if self.active and tag==self.active[-1]:
            self.active.pop()
    def handle_data(self,data):
        if self.active and data.strip():
            self.parts.append(data.strip())


def verify_one(row,url,session):
    maker=str(row.get("Hersteller","")).strip()
    roots=maker_aliases(maker)
    if not roots or not allowed_host(url,roots):
        return {"status":"Kein freigegebener Herstellerlink","http":"","url":"","evidence":""}
    current=url
    response=None
    for _ in range(3):
        try:
            response=session.get(current,headers=HEADERS,timeout=(5,12),
                                 allow_redirects=False)
        except requests.RequestException as exc:
            return {"status":type(exc).__name__,"http":"","url":current,"evidence":""}
        if response.status_code in (301,302,303,307,308):
            location=response.headers.get("Location","")
            target=urljoin(current,location) if location else ""
            if not allowed_host(target,roots):
                return {"status":"Weiterleitung auf Fremddomain/unsichere URL",
                        "http":str(response.status_code),"url":current,"evidence":""}
            current=target
            continue
        break
    if response is None:
        return {"status":"Keine HTTP-Antwort","http":"","url":current,"evidence":""}
    if response.status_code in (301,302,303,307,308):
        return {"status":"Zu viele Weiterleitungen","http":str(response.status_code),
                "url":current,"evidence":""}
    if response.status_code!=200:
        return {"status":"HTTP-Zugriff fehlgeschlagen",
                "http":str(response.status_code),"url":current,"evidence":""}
    if len(response.content)>3_000_000:
        return {"status":"HTML-Datei zu groß","http":"200","url":current,"evidence":""}
    ctype=response.headers.get("Content-Type","").lower()
    if "html" not in ctype:
        return {"status":"Kein HTML-Inhalt","http":"200","url":current,"evidence":""}
    sample=response.text[:4000].casefold()
    if any(marker in sample for marker in BOT_MARKERS):
        return {"status":"Bot-/Cloudflare-Sperre","http":"200","url":current,"evidence":""}
    parser=Headings()
    try:
        parser.feed(response.text)
    except (ValueError,TypeError):
        return {"status":"HTML nicht lesbar","http":"200","url":current,"evidence":""}
    heading=" ".join(parser.parts)
    model=str(row.get("Typ / Modell","")).strip()
    product=str(row.get("Produkt","")).strip()
    if not heading:
        return {"status":"Kein prüfbarer Produkttitel","http":"200",
                "url":current,"evidence":""}
    title=compact(heading)
    if model:
        whole=compact(model)
        family=compact(model_search_key(model))
        if len(whole)>=3 and whole in title:
            return {"status":"Produkttyp auf Herstellerseite bestätigt",
                    "http":"200","url":current,"evidence":heading[:350]}
        if len(family)>=3 and family in title:
            return {"status":"Produktfamilie auf Herstellerseite bestätigt – Ausführung offen",
                    "http":"200","url":current,"evidence":heading[:350]}
        return {"status":"HTTP 200 – gesuchter Typ im Seitentitel nicht bestätigt",
                "http":"200","url":current,"evidence":heading[:200]}
    words={w for w in useful_product_tokens(product,maker) if len(w)>=4 and not w.isdigit()}
    matched={w for w in words if w in normalize(heading)}
    if len(matched)>=2:
        return {"status":"Produktbeschreibung auf Herstellerseite bestätigt – Variante offen",
                "http":"200","url":current,"evidence":heading[:350]}
    return {"status":"HTTP 200 – Produktbezug unbestätigt",
            "http":"200","url":current,"evidence":heading[:200]}


def verify_row(row,session,limit=3):
    raw=str(row.get("Kandidaten_JSON") or "[]")
    try:
        candidates=json.loads(raw)
        if not isinstance(candidates,list):
            candidates=[]
    except (TypeError,ValueError):
        candidates=[]
    urls=[]
    # Only official-host URLs, never third-party index links
    for candidate in candidates[:5]:
        if isinstance(candidate,dict) and candidate.get("source_kind")=="Herstellerdomain":
            url=str(candidate.get("url") or "")
            if url and url not in urls:
                urls.append(url)
    if not urls and row.get("Bester_Treffer"):
        urls=[str(row["Bester_Treffer"])]
    out={"Produktseiten_Pruefstatus":"Kein Hersteller-Produktseitenkandidat",
         "Produktseiten_HTTP":"","Produktseiten_Bestaetigt":"Nein",
         "Produktseiten_Beleg":"","Produktseiten_Verifizierte_URL":"",
         "Produktseiten_Pruefdiagnose":""}
    attempts=[]
    for url in urls[:limit]:
        result=verify_one(row,url,session)
        attempts.append(url+" -> "+result["status"]+
                        (" ("+result["http"]+")" if result["http"] else ""))
        if out["Produktseiten_Pruefstatus"]=="Kein Hersteller-Produktseitenkandidat":
            out["Produktseiten_Pruefstatus"]=result["status"]
            out["Produktseiten_HTTP"]=result["http"]
            out["Produktseiten_Beleg"]=result["evidence"]
        if "auf Herstellerseite bestätigt" in result["status"]:
            out["Produktseiten_Pruefstatus"]=result["status"]
            out["Produktseiten_HTTP"]=result["http"]
            out["Produktseiten_Bestaetigt"]="Ja"
            out["Produktseiten_Beleg"]=result["evidence"]
            out["Produktseiten_Verifizierte_URL"]=result["url"]
            break
    out["Produktseiten_Pruefdiagnose"]=" | ".join(attempts)
    return out


def verify_file(source,destination):
    with Path(source).open(encoding="utf-8-sig",newline="") as fd:
        rows=list(csv.DictReader(fd,delimiter=";"))
    sess=requests.Session()
    out=[]
    for row in rows:
        item={**row,**verify_row(row,sess)}
        out.append(item)
    path=Path(destination)
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for item in out for k in item))
    with path.open("w",encoding="utf-8-sig",newline="") as fd:
        writer=csv.DictWriter(fd,fieldnames=fields,delimiter=";")
        writer.writeheader();writer.writerows(out)
    summary={"zeilen":len(out),
             "herstellerseiten_inhaltlich_bestaetigt":sum(
                 r["Produktseiten_Bestaetigt"]=="Ja" for r in out),
             "bestellte_einzelartikel_mit_nachgewiesener_sku":0,
             "gesperrt_oder_http_fehler":sum(
                 "Sperre" in r["Produktseiten_Pruefstatus"] or
                 "HTTP-Zugriff fehlgeschlagen" in r["Produktseiten_Pruefstatus"]
                 for r in out),
             "status":dict(Counter(r["Produktseiten_Pruefstatus"] for r in out)),
             "ausgabe":str(path)}
    print("PRODUKTSEITEN_PRUEFUNG",json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("input");p.add_argument("output")
    opts=p.parse_args()
    verify_file(opts.input,opts.output)
