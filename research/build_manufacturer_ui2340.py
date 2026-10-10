"""v2.3.40: corrected manufacturer domains and explicit bot-block handling."""
from pathlib import Path
import ast,json
root=Path("/tmp/tga2340");p=root/"app.py"
s=p.read_text(encoding="utf-8")
assert 'APP_VERSION = "2.3.39"' in s
s=s.replace('APP_VERSION = "2.3.39"','APP_VERSION = "2.3.40"',1)
marker='# Manufacturer website search v2.3.39'
assert marker in s
s=s[:s.index(marker)]
ui=Path("research/build_manufacturer_ui2339.py").read_text(encoding="utf-8")
ui=ast.literal_eval(next(n.value for n in ast.parse(ui).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="ui" for t in n.targets)))
ui=ui.replace('# Manufacturer website search v2.3.39','# Manufacturer website search v2.3.40')
ui=ui.replace('"schedel":["schedel-bad.de"]','"schedel":["schedel-badinnovation.de","schedel-bad.de"]')
ui=ui.replace('"witingsthal":["wittingsthal.de"]','"witingsthal":["wittigsthal.de"]')
ui=ui.replace('"wittingsthal":["wittingsthal.de"]','"wittingsthal":["wittigsthal.de"]')
ui=ui.replace('"emco":["emco-bath.com"]','"emco":["emco-bath.com/de/","emco-bath.com"]')
ui=ui.replace('"rockwool":["rockwool.com"]','"rockwool":["rockwool.com/de/","rockwool.com"]')
ui=ui.replace('"grohe":["grohe.de","grohe.com"]','"grohe":["grohe.de","grohe.com/de/"]')
# Domain entries can contain path: distinguish host from path, never prepend www to path.
ui=ui.replace('''for prefix in ("https://www.","https://"):
                found,status=_site_check(session,prefix+domain+"/",domain)''','''for prefix in ("https://www.","https://"):
                host=domain.split("/")[0]
                path="/"+domain.split("/",1)[1] if "/" in domain else "/"
                found,status=_site_check(session,prefix+host+path,host)''')
# Don't label HTTP 403 as a dead site; preserve official URL for browser opening.
ui=ui.replace('''    def _site_check(session,url,expected):
        try:''','''    def _site_check(session,url,expected):
        try:''')
ui=ui.replace('''            if response.status_code<400 and len(response.content)>100:
                return (response.url,"Erreichbar – offizielle Domain" if allowed else "Erreichbar – Weiterleitung prüfen")''','''            if response.status_code<400 and len(response.content)>100:
                return (response.url,"Erreichbar – offizielle Domain" if allowed else "Erreichbar – Weiterleitung prüfen")
            if response.status_code in (401,403,429):
                return (url,"Automatischer Zugriff gesperrt – im Browser prüfen")''')
ui=ui.replace('''        for domain in known:
            for prefix''','''        blocked=None
        for domain in known:
            for prefix''')
ui=ui.replace('''                if found:return (found,status)
        # Unknown manufacturers''','''                if found:
                    if status.startswith("Erreichbar"):return (found,status)
                    if blocked is None:blocked=(found,status)
        if blocked is not None:return blocked
        # Unknown manufacturers''')
ui=ui.replace('''                st.write("Erreichbare Websites:",int(_site_df["Herstellerwebsite"].astype(bool).sum()),"von",len(_site_df))''','''                st.write("Automatisch erreichbare Websites:",int(_site_df["Status"].astype(str).str.startswith("Erreichbar").sum()),"von",len(_site_df))
                st.caption("HTTP 403/429: Die Adresse ist bekannt, der automatische Zugriff ist blockiert. Bitte im Browser prüfen.")''')
s+=ui
ast.parse(s)
p.write_text(s,encoding="utf-8")
v=root/"version.json";d=json.loads(v.read_text(encoding="utf-8"));d["version"]="2.3.40";v.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding="utf-8")
print("PASS: corrected domain candidates and bot-block statuses")
