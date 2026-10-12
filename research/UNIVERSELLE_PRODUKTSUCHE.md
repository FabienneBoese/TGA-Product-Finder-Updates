# Universelle Produktsuche – technischer Stand vom 12.10.2026

## Ausgangspunkt

Ziel: herstellerunabhängige, automatisierte Recherche zu TGA-Produkten anhand
von Hersteller, Bezeichnung, Typ/Modell und optionaler Dimension; keine
vermutete Artikelnummer darf als bestätigt gespeichert werden.

Basis: 59 Positionen / 25 verschiedene Hersteller; 57 Positionen mit Hersteller,
22 mit Typ-/Modellangabe, 37 ohne.

## Implementierte Suchmodule

1. `research/universal_product_search.py`: gemeinsame Abfrageschnittstelle und
   Bewertung für Herstellerdomains, öffentliche Suchindizes und spätere APIs;
   Ergebnis je Produkt in semikolongetrennter CSV.
2. `research/manufacturer_sitemap_provider.py`: offizielle XML-Sitemaps und
   robots.txt als alternative herstellerübergreifende URL-Quelle, ohne
   Login, ohne Browserinteraktion, gecacht je Hersteller und mit strengem
   Allowlisting für Unternehmensdomains.
3. `research/verify_product_candidates.py`: lädt ausschließlich
   allowlist-bestätigte Herstellerlinks; prüft HTTP, Cloudflare-Inhalte,
   sichere Weiterleitungen und Produktnamen/Typ im tatsächlichen
   HTML-Titel bzw. in Überschriften.
4. Optionaler Brave Search API-Adapter mit `TGA_BRAVE_API_KEY`
   aus der Umgebung; Schlüssel niemals in die App, ZIPs oder ins Repo legen.
   Bing RSS nur experimentell, nicht als verlässliche Produktdatenquelle.

## Realitätsprüfung – GitHub Actions

Funktionstest: https://github.com/FabienneBoese/TGA-Product-Finder-Updates/actions/runs/38302904910

**39/39 Tests bestanden** (19 allgemeine Suche, 9 Sitemap, 11 HTML-Verifizierung).

Live-Test mit tatsächlicher 59er-Datei:
https://github.com/FabienneBoese/TGA-Product-Finder-Diagnose/actions/runs/38302930975

Verifizierter privater CSV-Bericht:
https://github.com/FabienneBoese/TGA-Product-Finder-Diagnose/blob/main/diagnosen/automatisch/TGA_Universalsuche_38302930975_attempt_1_Verifiziert.csv

Ergebnis: **5/59 tatsächliche Herstellerwebseiten mit HTTP 200 und
Typ-/Familienabgleich im HTML**:
- TROX FKRS-EU/DE/125/Z00: Produktfamilie erkannt, Ausführung OFFEN
- TROX FKRS-EU/DE/125/AA/Z43RM: Produktfamilie erkannt, Ausführung OFFEN
- TROX FV-EU: Typ im Seiteninhalt gefunden
- Reflex SERVITEC S: Typ im Seiteninhalt gefunden
- Kemper Figur 190 22: Typ im Seiteninhalt gefunden

**0/59 automatisch bestätigte Einzelartikel/SKU**; das ist
kein Scheitern der Typ-/Familienprüfung, sondern die ausdrückliche
Trennung zwischen Produktfamilie und artikelscharfer Zuordnung.

Wichtiges Negativergebnis: Bing RSS gab für Fachanfragen nach
TROX FKRS-EU oft vollkommen irrelevante Ergebnisse (z. B.
Domino's); selbst Site-Filter wurden teils ignoriert. Treffer allein
dürfen daher niemals einen offiziellen Herstellerbeleg darstellen.

Die Sitemap-Recherche ist universell, aber bei einigen Herstellern
fehlten passende Einträge oder maschinell erreichbare Sitemaps.
WIKA-Sitemaps waren weiterhin durch HTTP 403 gesperrt. Eine
manuell im Browser erreichbare Startseite zählt NICHT als
maschinenlesbare Herstellerdatenquelle.

## Lokale Verwendung

```bash
pip install requests
python research/universal_product_search.py /pfad/produkte.csv /pfad/index_kandidaten.csv --provider sitemap
python research/verify_product_candidates.py /pfad/index_kandidaten.csv /pfad/produkttreffer_verifiziert.csv
```

Eingabespalten: `Hersteller`, `Produkt`, `Typ / Modell` (CSV mit Semikolon).
Optional: `--provider auto` für Sitemap plus Brave Search API
(wenn `TGA_BRAVE_API_KEY` gesetzt ist), sonst öffentlicher RSS-Index.
Die Software schreibt keine automatisch bestätigten Artikelnummern
aus bloßen Indexhinweisen.

## Nächster Schritt

- [ ] Erweiterung der erkannten Hersteller über unabhängige Domain-Quellen
      ohne Hartcodierung pro Hersteller.
- [ ] Weitere zentrale Datenlieferungen und APIs mit Erlaubnis/Entitlements
      als Suchprovider anschließen (AUSSCHREIBEN.DE, OXOMI, ARGE, Icecat).
- [ ] Produktfamilien mit Auswahl von Bauteilart und Dimension auflösen.
- [ ] Erst anschließend artikelscharfe Serien-/SKU-/GTIN-Daten mit Quellenbelegen
      zuordnen und in Projektmappe übernehmen.
- [ ] Nach substantiell besserer Trefferqualität neue Suche als App-UI in
      installierbare Version integrieren und komplett testen.

**Wichtig:** Die neue Suche ist ein getesteter GitHub-Forschungskern,
noch kein installiertes Streamlit-Update. Aktuell veröffentlichter
App-Stand bleibt v2.3.43.
