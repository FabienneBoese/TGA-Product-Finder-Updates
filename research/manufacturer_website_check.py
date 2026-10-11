"""Homepage-only manufacturer availability check.

Scope: manufacturer identities and official reachable websites. Never search
product pages, article numbers, or documents in this diagnostic phase.
"""
import argparse
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests

from headless_article_research import domain_for
from manufacturer_domain_resolver import maker_key, domain_name, load_cache, save_cache

# Explicit manufacturer-owned regional/domain alternatives. An unrelated
# search-engine hit or previous cache entry cannot extend this allowlist.
OFFICIAL_ALIASES = {
    "heliosventilatoren.de": ("heliosventilatoren.de",),
    "wika.com": ("wika.com", "wika.de"),
    "villeroy-boch.de": ("villeroy-boch.de", "villeroy-boch.com"),
    "viega.de": ("viega.de", "viega.com"),
    "duravit.de": ("duravit.de", "duravit.com"),
    "kemper-group.com": ("kemper-group.com",),
    "emco-bath.com": ("emco-bath.com", "emco-world.com"),
    "clage.de": ("clage.de", "clage.com"),
    "hewi.de": ("hewi.de", "hewi.com"),
    "newo.de": ("newo.de", "newo.at"),
    "schedel-bad.de": ("schedel-bad.de", "schedel-badinnovation.de"),
    "kermi.com": ("kermi.com", "kermi.de"),
    "geberit.de": ("geberit.de", "geberit.com"),
}
# Prefer German landing pages when known; root and www are also attempted.
LANDING_PATHS = {
    "heliosventilatoren.de": ("/de/", "/"),
    "kemper-group.com": ("/de-de/", "/"),
    "duravit.com": ("/de-de/", "/"),
    "villeroy-boch.de": ("/",),
    "rockwool.com": ("/de/", "/"),
    "clage.com": ("/de/", "/"),
    "viega.com": ("/de/", "/"),
}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TGA-Product-Finder/2.3; Herstellerwebsite-Pruefung)"}
BLOCK_MARKERS = ("access denied", "verify you are human", "checking your browser",
                 "attention required! | cloudflare", "just a moment...")

def official_hosts(known):
    if not known:
        return ()
    return tuple(dict.fromkeys(OFFICIAL_ALIASES.get(known, (known,))))

def permitted_host(host, allowed):
    """Match only allowlisted domains and their subdomains, never lookalikes."""
    return bool(host and any(host == root or host.endswith("." + root) for root in allowed))

def candidate_urls(host):
    paths = LANDING_PATHS.get(host, ("/",))
    return list(dict.fromkeys(
        "https://" + prefix + host + path
        for path in paths for prefix in ("www.", "")
    ))

def probe(session, url, allowed):
    try:
        response = session.get(url, headers=HEADERS, timeout=(5, 9), allow_redirects=True)
        final_url = response.url
        final_host = domain_name(final_url)
        status_code = response.status_code
        if not permitted_host(final_host, allowed):
            return None, "Fremdweiterleitung " + final_host
        if status_code != 200:
            return None, "HTTP " + str(status_code) + " (" + final_host + ")"
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and "html" not in content_type and "xhtml" not in content_type:
            return None, "Kein HTML (" + content_type[:60] + ")"
        sample = response.text[:1200].lower()
        if any(marker in sample for marker in BLOCK_MARKERS):
            return None, "Bot-/Zugriffssperre (" + final_host + ")"
        if not final_url.startswith("https://"):
            return None, "Kein HTTPS"
        return final_url, "HTTP 200, HTML, erlaubte Herstellerdomain"
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.SSLError:
        return None, "TLS-Fehler"
    except requests.exceptions.ConnectionError:
        return None, "Verbindungs-/DNS-Fehler"
    except requests.RequestException as exc:
        return None, type(exc).__name__

def check_manufacturer(session, maker):
    if not str(maker or "").strip():
        return {"Herstellerdomain": "", "Herstellerwebsite": "",
                "Herstellerwebsite-Status": "Hersteller fehlt",
                "Website-erreichbar": "Nein", "Website-Pruefdiagnose": ""}
    primary = domain_for(maker)
    if not primary:
        return {"Herstellerdomain": "", "Herstellerwebsite": "",
                "Herstellerwebsite-Status": "Offizielle Domain unbekannt",
                "Website-erreichbar": "Nein", "Website-Pruefdiagnose": ""}
    allowed = official_hosts(primary)
    attempts = []
    # Check all official alternative domains, without promoting arbitrary URLs.
    for host in allowed:
        for url in candidate_urls(host):
            found, note = probe(session, url, allowed)
            attempts.append(url + " -> " + note)
            if found:
                return {"Herstellerdomain": domain_name(found), "Herstellerwebsite": found,
                        "Herstellerwebsite-Status": "Erreichbar: HTTP 200",
                        "Website-erreichbar": "Ja", "Website-Pruefdiagnose": " | ".join(attempts)}
    return {"Herstellerdomain": primary, "Herstellerwebsite": "",
            "Herstellerwebsite-Status": "Zugriff nicht bestätigt",
            "Website-erreichbar": "Nein", "Website-Pruefdiagnose": " | ".join(attempts)}

def run(source, destination):
    with open(source, encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    groups = {}
    for index, row in enumerate(rows):
        groups.setdefault(maker_key(row.get("Hersteller", "")), []).append(index)

    def check_group(item):
        key, indices = item
        with requests.Session() as session:
            result = check_manufacturer(session, rows[indices[0]].get("Hersteller", ""))
        return key, result

    with ThreadPoolExecutor(max_workers=8) as executor:
        checked = dict(executor.map(check_group, groups.items()))

    results = []
    for row in rows:
        result = dict(row)
        result.update(checked[maker_key(row.get("Hersteller", ""))])
        results.append(result)

    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in results for k in row))
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(results)
    # Cache only success; do not let outdated or bogus domains override verified ones.
    cache_path = target.with_name("herstellerdomains_cache.json")
    cache = load_cache(cache_path)
    for key, result in checked.items():
        if result["Website-erreichbar"] == "Ja":
            cache[key] = {"domain": result["Herstellerdomain"],
                          "homepage": result["Herstellerwebsite"],
                          "status": result["Herstellerwebsite-Status"]}
    save_cache(cache_path, cache)
    count = sum(x["Website-erreichbar"] == "Ja" for x in results)
    brands = {k: x for k, x in checked.items() if k}
    summary = {"rows": len(results), "manufacturers": len(brands),
               "with_manufacturer": sum(bool(maker_key(x.get("Hersteller"))) for x in rows),
               "reachable": count, "unreachable": len(results) - count,
               "reachable_manufacturers": sum(x["Website-erreichbar"] == "Ja" for x in brands.values()),
               "unknown_manufacturers": [k for k,x in brands.items() if not x["Herstellerdomain"]],
               "output": str(target)}
    print(json.dumps(summary, ensure_ascii=False))
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    run(args.input, args.output)
