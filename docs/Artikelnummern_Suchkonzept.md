# Herstellerübergreifendes Suchkonzept für Artikelnummern

## Ziel und Datenmodell
Originaldaten aus Excel und Projektdatenbank unverändert speichern. Getrennte Felder für Hersteller, Produktfamilie, Typ/Modell, Dimension, Ausführung, ursprüngliche Bestandskennung, recherchierte Herstellerartikelnummer, Herstellerquelle, Prüfstatus und Datum der Prüfung führen. Eine gefüllte Bestandskennung ist niemals automatisch eine verifizierte Artikelnummer.

## Suchkaskade
1. Datensatz normalisieren, ohne Originalwerte zu überschreiben. Maßeinheiten, Dimensionen, Bauart und Ausführungsmerkmale extrahieren; Hersteller-Aliasse vereinheitlichen.
2. Offizielle Herstellerdomain und mögliche Hersteller-Katalog-APIs, Produktseiten, Downloads, PDF-Kataloge und strukturierte Produktdaten ermitteln. Hersteller-Domainliste ist eine Hilfestellung, kein hartes Limit; unbekannte Hersteller werden über gesonderte Domain-Verifikation aufgenommen.
3. Exakte Suche mit Hersteller + Typ/Modell + Dimension + Ausführung. Danach alternative Schreibweisen, verkürzte Modelle und mögliche Bestandskennungen. Nicht von HTML-Scraping eines einzigen Suchmaschinenanbieters abhängig machen. Bei HTTP 403, 404, Rate Limits oder leeren Ergebnissen auf andere Quellen zurückfallen.
4. Offizielle Produktseiten und PDFs gezielt abrufen; Kennungen im Kontext von 'Artikelnummer', 'Art.-Nr.', 'Bestellnummer', 'Order No.', 'Product code' oder strukturierten Daten extrahieren. Katalogfamiliennummern, GTIN/EAN, Typ und Herstellerartikelnummer getrennt speichern.
5. Kandidaten auf Hersteller, Produkttyp, technische Parameter, Dimension und Ausführung abgleichen. Widersprüche schließen eine automatische Bestätigung aus. Mehrere Varianten bleiben auswählbar.
6. Bei Systemen wie Geberit Mapress Therm Produktfamilie beibehalten oder Bauteilgruppe (Rohr/Muffe) und Dimensionen zusammenfassen; Einzelartikel nur bei ausdrücklich gewählter konkreter Variante.
7. Dokumentensuche erst nach Abgleich der gewünschten Dokumentationsebene starten. Bei nicht eindeutigem Treffer Quellen und offene Merkmale anzeigen, statt eine Nummer zu erfinden.

## Statusmodell
- Keine Nummer ermittelt
- Bestandskennung ungeprüft
- Nummernkandidat mit Quellenlink
- Wahrscheinlich passend (Merkmale weitgehend übereinstimmend)
- Herstellerseitig bestätigt (offizielle Quelle und sämtliche zwingenden Merkmale stimmen)
- Mehrdeutig / manuelle Auswahl erforderlich
- Widerspruch / falsche Zuordnung

## Qualitätssicherung
- Alle 59 ursprünglichen Komponenten als Regressionstest mit Originalwerten prüfen; Änderungen gegenüber der Excel-Eingabe sichtbar machen.
- Separate Fälle für MCX3, AG.STAHLFORM505, MS-2LN110, 7985.10, 09506, FKRS-EU/DE/125/Z00 und Mapress Therm.
- Verifizieren, dass kein Modell ohne externe Quelle als bestätigte Artikelnummer ausgegeben wird.
- Herstellerquellen mit URL, Abrufdatum, HTTP-Status und extrahiertem Textausschnitt protokollieren.
- Messwerte: Trefferquote pro Hersteller, eindeutige Bestätigungen, mehrdeutige Treffer, falsche Positive und Quellenfehler.
- Offline: Bereits recherchierte Herstellerquellen und PDFs projektbezogen zwischenspeichern; Online-Suche nur bei Verbindung.

## Umsetzungsstand
v2.3.21 korrigiert die Diagnose-Anzeige und bewahrt ursprüngliche Bestandskennungen als ungeprüft. Die vollautomatische Extraktion und Verifikation aus Herstellerquellen ist **noch nicht implementiert**. Die in v2.3.20 vorhandene Google-HTML-Suche ist nur ein Prototyp und erfüllt das hier beschriebene Suchkonzept noch nicht.
