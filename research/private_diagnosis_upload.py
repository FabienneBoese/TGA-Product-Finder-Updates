"""Private GitHub diagnosis upload. Never sends data without explicit opt-in."""
import base64
import csv
import io
import os
import re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
import requests

DESTINATION="FabienneBoese/TGA-Product-Finder-Diagnose"
def diagnosis_csv(rows):
    out=io.StringIO()
    rows=list(rows)
    fields=list(dict.fromkeys(k for row in rows for k in row.keys()))
    writer=csv.DictWriter(out,fieldnames=fields,delimiter=";",extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff"+out.getvalue()).encode("utf-8-sig") if False else ("\ufeff"+out.getvalue()).encode("utf-8")

def save_diagnosis(rows,folder):
    target=Path(folder)
    target.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path=target/("TGA_Artikelrecherche_"+stamp+".csv")
    path.write_bytes(diagnosis_csv(rows))
    return path

def upload_diagnosis(path,token,repository=DESTINATION,session=None):
    """Create-only upload. A collision is reported, never overwritten."""
    if not token or not token.strip():
        raise ValueError("GitHub-Zugriffstoken fehlt")
    if repository!=DESTINATION:
        raise ValueError("Nur das freigegebene private Diagnose-Repository ist erlaubt")
    if not re.fullmatch(r"TGA_Artikelrecherche_\d{8}T\d{6}Z\.csv",Path(path).name):
        raise ValueError("Ungültiger Diagnose-Dateiname")
    name=quote("diagnosen/"+Path(path).name,safe="/")
    url="https://api.github.com/repos/"+repository+"/contents/"+name
    payload={"message":"Add TGA article diagnosis "+Path(path).name,
             "content":base64.b64encode(Path(path).read_bytes()).decode("ascii")}
    headers={"Authorization":"Bearer "+token.strip(),"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
    client=session or requests.Session()
    response=client.put(url,json=payload,headers=headers,timeout=25)
    if response.status_code!=201:
        # Never include response body, request or token in an exception.
        raise RuntimeError("GitHub-Upload fehlgeschlagen (HTTP "+str(response.status_code)+"). Lokale CSV bleibt erhalten.")
    return "https://github.com/"+repository+"/blob/main/"+name
