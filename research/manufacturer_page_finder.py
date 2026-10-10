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

def classify(session, row):
    maker = row.get("Hersteller", "")
    product = row.get("Produkt", "")
    model = row.get("Typ / Modell", "")
    domain = domain_for(maker)
    result = dict(row)
    result.update({"Herstellerdomain": domain, "Herstellerseiten-Kandidaten": "",
                   "Produktseiten-URL": "", "Suchstatus": "", "Suchdiagnose": ""})
    if not domain:
        result["Suchstatus"] = "Hersteller fehlt" if not maker.strip() else "Herstellerdomain unbekannt"
        return result
    urls, diagnosis = discover(session, domain, product, model, maker)
    result["Herstellerseiten-Kandidaten"] = " | ".join(urls)
    result["Suchdiagnose"] = diagnosis
    scored = []
    for url in urls:
        if not url.startswith("https://") or not same_host(url, domain):
            continue
        try:
            response = session.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
            if response.status_code != 200 or not same_host(response.url, domain):
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
    if scored:
        scored.sort(reverse=True)
        result["Produktseiten-URL"] = scored[0][1]
        result["Suchstatus"] = "Produktseiten-Kandidat (Prüfung erforderlich)"
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
        groups.setdefault(domain_for(row.get("Hersteller", "")) or "unknown", []).append((index, row))
    def process_group(items):
        with requests.Session() as session:
            return [(index, classify(session, row)) for index, row in items]
    with ThreadPoolExecutor(max_workers=5) as pool:
        batches = list(pool.map(process_group, groups.values()))
    results = [result for _, result in sorted((pair for batch in batches for pair in batch), key=lambda item: item[0])]
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
