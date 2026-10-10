"""Phase 1: find official manufacturer product pages, without document or article extraction."""
import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from headless_article_research import domain_for, discover, product_page_score, HEADERS
from manufacturer_article_engine import same_host
from manufacturer_domain_resolver import resolve, load_cache, save_cache

def classify(session, row, domain_info=None):
    maker = row.get("Hersteller", "")
    product = row.get("Produkt", "")
    model = row.get("Typ / Modell", "")
    domain, homepage, website_status = domain_info if domain_info is not None else (domain_for(maker), "https://www." + domain_for(maker) + "/" if domain_for(maker) else "", "Bekannte Domain; nicht geprüft")
    result = dict(row)
    result.update({"Herstellerdomain": domain, "Herstellerwebsite": homepage, "Herstellerwebsite-Status": website_status, "Herstellerseiten-Kandidaten": "",
                   "Produktseiten-URL": "", "Suchstatus": "", "Suchdiagnose": ""})
    if not domain:
        result["Suchstatus"] = "Hersteller fehlt" if not maker.strip() else "Herstellerdomain unbekannt"
        return result
    urls, diagnosis = discover(session, domain, product, model, maker)
    result["Herstellerseiten-Kandidaten"] = " | ".join(urls)
    result["Suchdiagnose"] = diagnosis
    scored = []
    blocked = []
    redirected = []
    for url in urls:
        if not url.startswith("https://") or not same_host(url, domain):
            continue
        try:
            response = session.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
            if response.status_code in (403, 429):
                blocked.append(f"{url} HTTP {response.status_code}")
                continue
            if not same_host(response.url, domain):
                redirected.append(f"{url} -> {response.url}")
                continue
            if response.status_code != 200:
                continue
            if "pdf" in response.headers.get("Content-Type", "").lower():
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            title = (soup.title.get_text(" ", strip=True) if soup.title else "")
            title += " " + " ".join(h.get_text(" ", strip=True) for h in soup.select("h1")[:2])
            score = product_page_score(response.url, title, product, model)
            if score > 0:
                scored.append((score, response.url))
        except requests.RequestException:
            continue
    if blocked or redirected:
        result["Suchdiagnose"] = " | ".join(filter(None, [diagnosis, *blocked, *redirected]))
    if scored:
        scored.sort(reverse=True)
        result["Produktseiten-URL"] = scored[0][1]
        result["Suchstatus"] = "Produktseiten-Kandidat (Prüfung erforderlich)"
    elif blocked:
        result["Suchstatus"] = "Produktseite nicht prüfbar – Zugriff gesperrt (HTTP 403/429)"
    elif redirected:
        result["Suchstatus"] = "Weiterleitung auf Fremddomain – manuell prüfen"
    elif urls:
        result["Suchstatus"] = "Herstellerlinks gefunden, Produktseite unbestätigt"
    else:
        result["Suchstatus"] = "Keine Herstellerseite gefunden"
    return result

def run(source, destination):
    with open(source, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    groups = {}
    for index, row in enumerate(rows):
        groups.setdefault(str(row.get("Hersteller", "")).casefold().strip(), []).append((index, row))
    cache_path = str(Path(destination).with_name("herstellerdomains_cache.json"))
    cache = load_cache(cache_path)
    def process_group(items):
        with requests.Session() as session:
            maker = items[0][1].get("Hersteller", "")
            info = resolve(session, maker, cache, domain_for(maker))
            return [(index, classify(session, row, info)) for index, row in items]
    with ThreadPoolExecutor(max_workers=5) as pool:
        batches = list(pool.map(process_group, groups.values()))
    results = [result for _, result in sorted((pair for batch in batches for pair in batch), key=lambda item: item[0])]
    save_cache(cache_path, cache)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in results for k in row))
    with open(destination, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, delimiter=";", fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({"rows": len(results),
                      "with_urls": sum(bool(r["Herstellerseiten-Kandidaten"]) for r in results),
                      "page_candidates": sum(bool(r["Produktseiten-URL"]) for r in results),
                      "output": str(destination)}))
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    run(args.input, args.output)
