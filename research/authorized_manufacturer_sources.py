"""Approved machine-to-machine product data sources for manufacturer research.

This module NEVER circumvents anti-bot measures or treats a browser-only link as
machine-readable access. A machine-readable source is usable only with a
contractually permitted catalog feed or configured API entitlement.

Scope today: WIKA BMEcat catalogs and an authorized OXOMI portal (potential
Villeroy & Boch source, subject to portal content and access rights).
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import requests
from defusedxml import ElementTree as SafeET

OXOMI_ENDPOINT = "https://oxomi.com/portals/api/v2/product/data"


@dataclass(frozen=True)
class MachineSource:
    manufacturer: str
    source_type: str
    status: str
    reason: str
    evidence: str

    def to_dict(self):
        return asdict(self)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].upper()


def _first_text(element, tags: tuple[str, ...]) -> str:
    wanted = {x.upper() for x in tags}
    for child in element.iter():
        if _local(child.tag) in wanted and child.text and child.text.strip():
            return child.text.strip()
    return ""


def parse_bmecat(data: bytes | str, maximum: int = 200000) -> list[dict[str, str]]:
    """Parse a *provided and authorized* BMEcat feed (1.2 / 2005).

    No manufacturer website is accessed. Supplying a legitimate catalog is
    independent of a manufacturer's bot-protected public website.
    """
    if not isinstance(data, (bytes, str)) or len(data) > 75_000_000:
        raise ValueError("Katalogformat oder Dateigröße nicht unterstützt")
    if maximum < 1:
        raise ValueError("maximum muss positiv sein")
    root = SafeET.fromstring(data)
    records: list[dict[str, str]] = []
    for element in root.iter():
        if _local(element.tag) not in ("PRODUCT", "ARTICLE"):
            continue
        product_id = _first_text(element, ("SUPPLIER_PID", "SUPPLIER_AID"))
        if not product_id:
            continue
        records.append({
            "artikelnummer": product_id,
            "bezeichnung": _first_text(element, ("DESCRIPTION_SHORT", "ARTICLE_NAME", "PRODUCT_NAME")),
            "hersteller": _first_text(element, ("MANUFACTURER_NAME",)),
            "gtin": _first_text(element, ("EAN", "EAN_UPC", "INTERNATIONAL_PID")),
            "quelle": "freigegebener BMEcat-Katalog",
        })
        if len(records) >= maximum:
            break
    return records


def oxomi_access_token(secret: str, portal: str, user: str,
                       epoch_days: int, roles: str = "") -> str:
    """Apply the OXOMI documented shared-secret token scheme.

    Keep the secret server-side; never add it to the browser, logs or GitHub.
    """
    if not all((secret, portal, user)):
        raise ValueError("OXOMI-Portal, Benutzer und Shared Secret erforderlich")
    inner = hashlib.md5((secret + portal + user + str(epoch_days) + roles).encode("utf-8")).hexdigest()
    return hashlib.md5((secret + inner).encode("utf-8")).hexdigest()


def oxomi_product_data(session: requests.Session, *,
                       portal: str, user: str, secret: str, supplier_number: str,
                       item_number: str, epoch_days: int,
                       access_approved: bool = False, roles: str = "") -> dict[str, Any]:
    """Access the documented OXOMI Product Data API with a granted entitlement.

    A portal is NOT assumed to contain Villeroy & Boch merely because OXOMI
    publishes example data for that manufacturer elsewhere.
    """
    if not access_approved:
        raise PermissionError("Autorisierung zur Nutzung des ausgewählten OXOMI-Portals fehlt")
    if not supplier_number.strip() or not item_number.strip():
        raise ValueError("Für die gezielte Datenabfrage fehlen Lieferanten- oder Artikelnummer")
    token = oxomi_access_token(secret, portal, user, epoch_days, roles=roles)
    response = session.post(
        OXOMI_ENDPOINT,
        params={"portal": portal, "user": user, "language": "de",
                "roles": roles, "accessToken": token},
        json={
            "outputMode": "normal",
            "queries": {"attachments": {"type": "json"}},
            "products": [{"itemNumber": item_number,
                          "supplierNumber": supplier_number}],
        },
        timeout=(5, 25),
    )
    if response.status_code in (401, 403):
        raise PermissionError("OXOMI hat die Portalberechtigung abgelehnt")
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or not result.get("success", False):
        raise ValueError("Keine gültige OXOMI-Produktantwort")
    products = result.get("products", [])
    if not isinstance(products, list):
        raise ValueError("Unerwartetes OXOMI-Produktformat")
    matched = [x for x in products if isinstance(x, dict)
               and x.get("resolved")
               and x.get("itemNumber") == item_number
               and x.get("supplierNumber") == supplier_number]
    return {"source": "OXOMI autorisierter Produktfeed",
            "products": matched,
            "matched": bool(matched),
            "portal": portal}


def planned_access(manufacturer: str, *,
                   wika_catalog: str | None = None,
                   oxomi_portal: str | None = None,
                   oxomi_approved: bool = False) -> MachineSource:
    """Return an honest configuration state; no fake 200 or verified access."""
    maker = (manufacturer or "").casefold()
    if "wika" in maker:
        path = Path(wika_catalog) if wika_catalog else None
        if path is not None and path.is_file():
            try:
                records = parse_bmecat(path.read_bytes())
                if records:
                    return MachineSource("WIKA", "BMEcat",
                        "KATALOG_BEREIT", f"{len(records)} Katalogartikel technisch eingelesen",
                        "Vom Anwender bereitgestellte Katalogdatei; Quelle/Berechtigung gesondert prüfen")
                return MachineSource("WIKA", "BMEcat", "KATALOG_LEER",
                                     "Keine Artikel im Katalog erkannt", "")
            except (OSError, ValueError, SafeET.ParseError) as exc:
                return MachineSource("WIKA", "BMEcat", "KATALOG_FEHLER",
                                     type(exc).__name__, "")
        return MachineSource("WIKA", "BMEcat", "FREIGABE_AUSSTEHEND",
                             "Offizieller elektronischer Katalog oder Zugangsdaten erforderlich",
                             "https://www.wika.com/de-de/e_katalog.WIKA")
    if "villeroy" in maker and "boch" in maker:
        if oxomi_portal and oxomi_approved:
            return MachineSource("Villeroy & Boch", "OXOMI",
                                 "API_KONFIGURIERT_NICHT_LIVE_GETESTET",
                                 "Portalzugriff muss mit freigegebenen Artikeln live nachgewiesen werden",
                                 "https://oxomi.com/system/api/product")
        return MachineSource("Villeroy & Boch", "OXOMI",
                             "FREIGABE_AUSSTEHEND",
                             "Portalberechtigung und Hersteller-Datenfreigabe fehlen",
                             "https://oxomi.com/system/api/product")
    return MachineSource(manufacturer, "Direkt/sonstige Quellen",
                         "NICHT_IN_DIESEM_MODUL", "Bestehende Hersteller-Recherche nutzen", "")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--wika-catalog", default=os.getenv("TGA_WIKA_BMECAT_FILE"))
    p.add_argument("--oxomi-portal", default=os.getenv("TGA_OXOMI_PORTAL"))
    p.add_argument("--oxomi-approved", action="store_true")
    args = p.parse_args()
    results = [planned_access("WIKA", wika_catalog=args.wika_catalog),
               planned_access("Villeroy & Boch", oxomi_portal=args.oxomi_portal,
                              oxomi_approved=args.oxomi_approved)]
    print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
