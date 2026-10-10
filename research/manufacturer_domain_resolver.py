"""Discover official manufacturer homepages, with a persistent reviewed-domain cache.

Search engines are discovery sources only: an unreviewed search hit is never
silently promoted to a verified official manufacturer website.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TGA-Product-Finder/1.0)"}
EXCLUDE = ("wikipedia.org", "amazon.", "ebay.", "idealo.", "linkedin.", "facebook.",
           "instagram.", "youtube.", "northdata.", "wlw.", "wer-liefert-was.")
COMMON = {"gmbh", "ag", "kg", "co", "deutschland", "gruppe", "group", "technik",
          "sanitaer", "sanitär", "heizung", "und", "the", "company", "hersteller"}

def maker_key(maker):
    return " ".join(str(maker or "").casefold().strip().split())

def domain_name(url):
    host = urlparse(url).hostname or ""
    return host.lower().removeprefix("www.")

def search_links(session, maker):
    query = str(maker).strip() + " offizielle Website Hersteller"
    links = []
    for endpoint, params in (
        ("https://www.bing.com/search", {"q": query}),
        ("https://www.bing.com/search", {"q": query, "format": "rss"}),
        ("https://www.google.com/search", {"q": query}),
        ("https://html.duckduckgo.com/html/", {"q": query}),
    ):
        try:
            response = session.get(endpoint, params=params, headers=HEADERS, timeout=7)
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for a in soup.select("a[href], item link"):
                href = a.get("href") or a.get_text(strip=True)
                if href.startswith("/url?"):
                    href = parse_qs(urlparse(href).query).get("q", [""])[0]
                if "uddg=" in href:
                    href = parse_qs(urlparse(href).query).get("uddg", [href])[0]
                href = unquote(href)
                if href.startswith("https://") and domain_name(href) and href not in links:
                    links.append(href)
        except requests.RequestException:
            continue
    return links

def plausible(maker, url):
    host = domain_name(url)
    if not host or any(blocked in host for blocked in EXCLUDE):
        return False
    tokens = [t for t in re.findall(r"[a-z0-9]+", maker_key(maker)) if len(t) >= 4 and t not in COMMON]
    compact = re.sub(r"[^a-z0-9]", "", host.split(".")[0])
    return bool(tokens) and any(t in compact for t in tokens)

def _verified_cached_entry(saved):
    """Only explicitly verified cached entries may skip a fresh network check."""
    return (isinstance(saved, dict)
            and saved.get("verified") is True
            and bool(saved.get("domain"))
            and bool(saved.get("homepage"))
            and domain_name(saved["homepage"]) == saved["domain"])


def resolve(session, maker, cache, known_domain=""):
    """Return (domain, homepage, provenance). Cache stores only reviewed or checked entries."""
    key = maker_key(maker)
    if not key:
        return "", "", "Hersteller fehlt"
    saved = cache.get(key, {})
    if _verified_cached_entry(saved):
        return saved["domain"], saved["homepage"], saved.get("status", "Verifizierter Cache")
    candidates = search_links(session, maker)
    known_domain = domain_name(known_domain) if "://" in known_domain else known_domain.lower().removeprefix("www.")
    if known_domain:
        candidates.insert(0, "https://www." + known_domain + "/")
    for candidate in candidates:
        if not plausible(maker, candidate) and domain_name(candidate) != known_domain:
            continue
        host = domain_name(candidate)
        for homepage in ("https://www." + host + "/", "https://" + host + "/"):
            try:
                response = session.get(homepage, headers=HEADERS, timeout=7, allow_redirects=True)
                final = domain_name(response.url)
                if response.status_code != 200 or not response.url.startswith("https://"):
                    continue
                # A redirect to a different domain is never proof of manufacturer identity.
                if final != host and final != known_domain:
                    continue
                status = "Website erreichbar; Herstellerzuordnung prüfen"
                if known_domain and final == known_domain:
                    status = "Bekannte Herstellerdomain; Website erreichbar"
                cache[key] = {"domain": final, "homepage": response.url, "status": status, "verified": True}
                return final, response.url, status
            except requests.RequestException:
                continue
    if known_domain:
        return known_domain, "https://www." + known_domain + "/", "Bekannte Domain; Erreichbarkeit nicht bestätigt"
    return "", "", "Keine Herstellerwebsite bestätigt"

def load_cache(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def save_cache(path, cache):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
