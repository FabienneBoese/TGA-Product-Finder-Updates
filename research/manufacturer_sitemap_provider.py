"""Read official, public manufacturer sitemaps as a generic product URL source.

A URL listed in a manufacturer's sitemap is a DISCOVERY LEAD, not a verified
article, SKU, accessible product page, or license for document downloads.
This crawler never visits arbitrary third-party URLs from XML/robots or fetches
product pages; all roots are independently allowlisted.
"""
from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse, unquote
import re
import xml.etree.ElementTree as ET

import requests

from universal_product_search import (
    SearchHit, allowed_host, compact, maker_aliases, maker_domain,
    model_search_key, normalize, useful_product_tokens,
)

XML_LIMIT=1_800_000
MAX_CHILD_SITEMAPS=10
MAX_URLS_PER_DOMAIN=35_000
HEADERS={"User-Agent":"TGA-Product-Finder/2.4 (+official sitemap discovery)"}


def _local(tag):
    return tag.rsplit("}",1)[-1].lower()


def parse_sitemap(body):
    """Return (type, official-URL-strings), or ('',[]) for invalid content."""
    if len(body)>XML_LIMIT:
        return "",[]
    try:
        root=ET.fromstring(body)
    except (ValueError,ET.ParseError,TypeError):
        return "",[]
    kind=_local(root.tag)
    if kind not in ("sitemapindex","urlset"):
        return "",[]
    child_tag="sitemap" if kind=="sitemapindex" else "url"
    result=[]
    for elem in root:
        if _local(elem.tag)!=child_tag:
            continue
        link=next((node.text.strip() for node in elem if _local(node.tag)=="loc" and node.text),None)
        if link:
            result.append(link)
    return kind,result


def _rank_sitemap_link(url,model,product,maker):
    """Cheap URL-only discovery rank. This is not a page verification."""
    path=unquote(urlparse(url).path)
    if "&nbsp;" in url.lower() or "&#" in url.lower():
        return -1
    path_flat=compact(path)
    if not path_flat:
        return -1
    excluded=("/blog/","/news/","/kontakt","/contact","/impressum",
              "/datenschutz","/privacy","/terms","/unternehmen",
              "/company","/career","/jobs","/presse","/service/",
              "/newscenter/","/trox-newscenter/","/aktuelles/","/neuigkeiten/")
    if any(x in path.lower() for x in excluded):
        return -1
    if path.lower().endswith((".jpg",".png",".pdf",".docx",".xml",".zip")):
        return -1
    name=model_search_key(model)
    product_words=[w for w in useful_product_tokens(product,maker)
                   if len(w)>=4 and not w.isdigit()]
    found=sum(w in normalize(path) for w in set(product_words))
    if name:
        full=bool(len(compact(model))>=3 and compact(model) in path_flat)
        family=bool(len(compact(name))>=3 and compact(name) in path_flat)
        if not (full or family):
            return -1
        language=8 if "/de/" in path.lower() or "/de-de/" in path.lower() else 0
        return (80 if full else 40)+min(18,6*found)+language
    if found>=2:
        return 30+6*found
    return -1


class OfficialSitemap:
    """Cache sitemap indexes per manufacturer across the entire Excel test."""
    name="official_sitemap"
    def __init__(self,session=None):
        self.session=session or requests.Session()
        self.cache={}
        self.messages={}
        self.last_error=""

    def _download(self,url,roots):
        if not allowed_host(url,roots):
            return None
        try:
            response=self.session.get(url,headers=HEADERS,timeout=(4,8),
                                     allow_redirects=True)
            if response.status_code!=200 or not allowed_host(response.url,roots):
                return None
            if len(response.content)>XML_LIMIT:
                return None
            if b"<!DOCTYPE" in response.content[:2000].upper():
                return None
            return response.content
        except requests.RequestException:
            return None

    def _sitemap_candidates(self,domain,roots):
        host="www."+domain
        robots=self._download("https://"+host+"/robots.txt",roots)
        sitemaps=[]
        if robots and len(robots)<150_000:
            for line in robots.decode("utf-8",errors="ignore").splitlines():
                if line.strip().lower().startswith("sitemap:"):
                    u=line.split(":",1)[1].strip()
                    if allowed_host(u,roots):
                        sitemaps.append(u)
        sitemaps += ["https://"+host+part for part in (
            "/sitemap.xml","/sitemapindex.xml","/sitemap-index.xml")]
        return list(dict.fromkeys(sitemaps))

    def _collect(self,maker):
        domain=maker_domain(maker)
        if not domain:
            return []
        if domain in self.cache:
            return self.cache[domain]
        roots=maker_aliases(maker)
        visited=set()
        candidates=self._sitemap_candidates(domain,roots)
        collected=[]
        child_queue=[]
        # Stop after the first usable master sitemap, not the first HTTP 200.
        for url in candidates[:5]:
            if url in visited: continue
            visited.add(url)
            payload=self._download(url,roots)
            if payload is None:continue
            kind,links=parse_sitemap(payload)
            if kind=="urlset":
                collected.extend(u for u in links if allowed_host(u,roots))
                break
            if kind=="sitemapindex":
                child_queue=links
                break

        if child_queue:
            def priority(u):
                path=urlparse(u).path.casefold()
                if "/de/" in path or path.endswith("/de/sitemap.xml") or "de-de" in path:
                    return (0,u)
                if "/en/" in path or "/us/" in path or "/uk/" in path:
                    return (3,u)
                if any(x in path for x in ("product","produkt","catalog")):
                    return (1,u)
                return (2,u)
            queue=sorted(set(u for u in child_queue if allowed_host(u,roots)),
                         key=priority)[:MAX_CHILD_SITEMAPS]
            for child in queue:
                if child in visited:continue
                visited.add(child)
                payload=self._download(child,roots)
                if payload is None:continue
                kind,links=parse_sitemap(payload)
                if kind=="urlset":
                    collected.extend(u for u in links if allowed_host(u,roots))
                elif kind=="sitemapindex":
                    # One additional level only; bounded to avoid giant catalogs.
                    for sub in [u for u in links if allowed_host(u,roots)][:4]:
                        if sub in visited:continue
                        visited.add(sub)
                        inner=self._download(sub,roots)
                        if inner is None:continue
                        subtype,urls=parse_sitemap(inner)
                        if subtype=="urlset":
                            collected.extend(u for u in urls if allowed_host(u,roots))
                        if len(collected)>=MAX_URLS_PER_DOMAIN:break
                if len(collected)>=MAX_URLS_PER_DOMAIN:break
        collected=list(dict.fromkeys(collected))[:MAX_URLS_PER_DOMAIN]
        self.cache[domain]=collected
        self.messages[domain]=(str(len(collected))+" offizielle Sitemap-URLs"
                               if collected else "Keine abrufbare XML-Sitemap")
        return collected

    def search_for(self,row,limit=16):
        maker=str(row.get("Hersteller","")).strip()
        model=str(row.get("Typ / Modell","")).strip()
        product=str(row.get("Produkt","")).strip()
        if not maker or not maker_domain(maker):
            self.last_error="Keine bestätigte Herstellerdomain"
            return []
        urls=self._collect(maker)
        self.last_error=self.messages.get(maker_domain(maker),"")
        scored=[]
        for url in urls:
            rank=_rank_sitemap_link(url,model,product,maker)
            if rank<0:continue
            path=unquote(urlparse(url).path).strip("/")
            title=(path.split("/")[-1] if path else "").replace("-"," ").replace("_"," ")
            scored.append((rank,SearchHit(title,url,"Im offiziellen XML-Sitemap-Index",
                                          self.name)))
        return [hit for _,hit in sorted(scored,key=lambda x:(-x[0],x[1].url))[:limit]]
