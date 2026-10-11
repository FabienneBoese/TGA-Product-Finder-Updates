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

def _check_homepage(session, host, known=False):
    """Validate a homepage without silently trusting an unrelated redirect."""
    host = domain_name("https://" + str(host).strip("/"))
    if not host:
        return None
    for url in ("https://" + host + "/", "https://www." + host + "/"):
        try:
            response = session.get(url, headers=HEADERS, timeout=9, allow_redirects=True)
            final = domain_name(response.url)
            if response.status_code != 200 or not response.url.startswith("https://"):
                continue
            if final != host and final != "www." + host and not (
                final.endswith("." + host) or host.endswith("." + final)
            ):
                continue
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and "html" not in content_type:
                continue
            return final, response.url, ("Bekannte Herstellerdomain; Website erreichbar" if known
                                         else "Website erreichbar; Herstellerzuordnung prüfen")
        except requests.RequestException:
            continue
    return None


def resolve(session, maker, cache, known_domain=""):
    """Prefer a checked official known domain; do not promote a search hit over it."""
    key = maker_key(maker)
    if not key:
        return "", "", "Hersteller fehlt"
    known_domain = domain_name("https://" + known_domain) if known_domain else ""
    saved = cache.get(key, {})
    # Cache entries are hints, not permanent proof of current reachability.
    candidates = []
    if known_domain:
        candidates.append((known_domain, True))
    if saved.get("domain") and saved["domain"] != known_domain:
        candidates.append((saved["domain"], False))
    # A known domain remains authoritative even if it is temporarily blocked.
    for host, trusted in candidates:
        checked = _check_homepage(session, host, trusted)
        if checked:
            if trusted:
                cache[key] = {"domain": checked[0], "homepage": checked[1],
                              "status": checked[2]}
            return checked
    if known_domain:
        return known_domain, "https://" + known_domain + "/", "Bekannte Domain; Erreichbarkeit nicht bestätigt"
    # Search discovery is only used when no known official manufacturer domain exists.
    for candidate in search_links(session, maker):
        if not plausible(maker, candidate):
            continue
        checked = _check_homepage(session, domain_name(candidate))
        if checked:
            cache[key] = {"domain": checked[0], "homepage": checked[1],
                          "status": checked[2]}
            return checked
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
