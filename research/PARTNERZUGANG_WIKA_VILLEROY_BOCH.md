# Herstellerzugriff ohne manuelle Browseröffnung

**Ziel:** Maschinenlesbarer, rechtlich freigegebener Zugriff für den TGA Product Finder.
Diese Phase ersetzt manuelle Browserbestätigungen durch geprüfte Schnittstellen/Katalogfeeds.
Ein offizieller Herstellerlink allein gilt ausdrücklich NICHT als automatisierter Datenzugriff.

## Technischer Stand (12.10.2026)

- Direkte Herstellerwebsites: 23/25 automatisch per HTTP 200 erreicht.
- WIKA: offizielle Website/Shop/Blog aus GitHub Actions durch Cloudflare HTTP 403 blockiert.
- Villeroy & Boch: offizielle Web-/Profi-/Konzernseiten aus GitHub Actions HTTP 403 blockiert.
- Desktop-Browser kann beide Seiten manuell öffnen, ist kein Nachweis maschineller Erreichbarkeit.
- Adapter `research/authorized_manufacturer_sources.py` ist vorbereitet und durch Mocks getestet.
- **Keine gültigen API-Zugangsdaten und keine autorisierte Kataloglieferung vorhanden.**
- **Nicht** in das veröffentlichte Desktop-Update v2.3.43 integriert.

## WIKA: anzufragende Freigabe

WIKA bewirbt offizielle E-Kataloge, statische und dynamische Produktdatenexporte,
OCI/XML und (je nach Vereinbarung) weitere Formate.
Quelle: https://www.wika.com/de-de/e_katalog.WIKA

Für die Integration schriftlich klären:
- Regelmäßige maschinenlesbare Lieferung (BMEcat/XML oder zugeschnittenes CSV/Excel).
- Einbezogene Sortimente, Produktkennungen, URLs und technische Dokumente.
- Download-/Speicher-/Offline-/Aktualisierungsrechte und kommerzielle Weitergabe innerhalb der App.
- Zulässiger Abrufweg und Änderungs-/Löschhinweise.

Bei freigegebener BMEcat-Lieferung kann der lokale Parser automatisiert einlesen;
die Website-Sperre bleibt davon unabhängig.

## Villeroy & Boch: anzufragende Freigabe

Es gibt Produktdaten des Herstellers auf OXOMI.
OXOMI dokumentiert eine REST API, die Portalkennung und ggf. API-Authentifizierung erfordert.
**Die Sichtbarkeit einzelner öffentlich zugänglicher PDF-Links berechtigt nicht zur
vollständigen Portalabfrage oder Weiterverbreitung.**

Quellen:
- https://oxomi.com/system/api/product
- https://oxomi.com/help/de/integration/authentifizierung
- https://pro.villeroy-boch.com/de/de/bad-und-wellness/service

Für die Integration schriftlich klären:
- Ein für die App lizenziertes OXOMI-Portal mit Villeroy-&-Boch-Produkten
  (oder gleichwertige offizielle Hersteller-Schnittstelle).
- Portalkennung, User-/Rollenmodell, Supplier-/Artikelnummernzuordnung.
- API-Token/Shared Secret, Berechtigungen, Rate-Limits, Datenumfang, Dokumentlizenzen.
- Zulässige Nutzung über einzelne Kunden, Projekte und spätere kostenpflichtige Lizenzen.
- Rechte für Offline-Cache und regelmäßige Synchronisierung.

Secrets ausschließlich in geschützter Serverkonfiguration speichern; niemals im GitHub-Repository,
in App-Logs, im Streamlit-Frontend oder in veröffentlichten Update-ZIPs ablegen.

## Abnahmekriterien

1. Je Hersteller ein automatischer, ohne menschlichen Eingriff wiederholbarer Test.
2. Nachweis tatsächlich gelieferter maschinenlesbarer Herstellerdaten über eine freigegebene
   Quelle (nicht nur HTTP 200 auf der API-Startseite).
3. Deutliche Trennung: Homepage erreichbar, API konfiguriert, API live erfolgreich,
   Katalog importiert, Berechtigung ausstehend und Zugriff blockiert.
4. Deduplikation, Quellenherkunft, Änderungsdatum, Lizenz-/Offline-Speicherrechte erfassen.
5. Bei fehlender Berechtigung: `FREIGABE_AUSSTEHEND`, niemals 25/25 vortäuschen.

Rotierende Proxys/CAPTCHA-Umgehung sind kein belastbares Lizenzprodukt-Konzept.
