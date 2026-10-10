"""v2.3.41: real programmatic browser fallback for manufacturer sites."""
from pathlib import Path
import ast,json
root=Path("/tmp/tga2341");p=root/"app.py"
s=p.read_text(encoding="utf-8")
assert 'APP_VERSION = "2.3.40"' in s
s=s.replace('APP_VERSION = "2.3.40"','APP_VERSION = "2.3.41"',1)
marker='# Manufacturer website search v2.3.40'
assert marker in s
prefix=s[:s.index(marker)]
# Reuse the exact prior UI, replacing only the manufacturer checker.
builder=ast.parse(Path('research/build_manufacturer_ui2340.py').read_text(encoding='utf-8'))
# build 2340 uses transformations; run builder against temp root to get exact UI
import runpy
runpy.run_path('research/build_manufacturer_ui2340.py',run_name='__main__') if False else None
ui=s[s.index(marker):]
start=ui.index('    def _site_check(')
end=ui.index('    def _site_find(',start)
ui=ui[:start]+'''    def _site_browser_check(url,expected):
        """Programmatic Chromium page load; returns success only after actual page response."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ("","Browsermodul fehlt: pip install playwright")
        try:
            with sync_playwright() as pw:
                # Use an existing Edge/Chrome install where available; otherwise Playwright Chromium.
                browser=None
                for channel in ("msedge","chrome",None):
                    try:
                        options={"headless":True,"timeout":15000}
                        if channel:options["channel"]=channel
                        browser=pw.chromium.launch(**options)
                        break
                    except Exception:
                        continue
                if browser is None:return ("","Kein Browser verfügbar – Chromium installieren")
                try:
                    page=browser.new_page(locale="de-DE")
                    response=page.goto(url,wait_until="domcontentloaded",timeout=20000)
                    if response is not None and response.status<400 and len(page.content())>100:
                        host=_site_host(page.url)
                        allowed=host==expected or host.endswith("."+expected)
                        return (page.url,"Browserzugriff erfolgreich" if allowed else "Browserzugriff – Weiterleitung prüfen")
                    if response is not None and response.status in (401,403,429):
                        return ("","Auch Browserzugriff gesperrt (HTTP "+str(response.status)+")")
                    return ("","Browser lieferte keine erreichbare Seite")
                finally:
                    browser.close()
        except Exception as exc:
            return ("","Browserprüfung fehlgeschlagen: "+str(exc)[:110])
    def _site_check(session,url,expected):
        try:
            response=session.get(url,timeout=9,allow_redirects=True,headers={"User-Agent":"Mozilla/5.0"})
            host=_site_host(response.url)
            allowed=(host==expected or host.endswith("."+expected))
            if response.status_code<400 and len(response.content)>100:
                return (response.url,"Erreichbar – offizielle Domain" if allowed else "Erreichbar – Weiterleitung prüfen")
            if response.status_code in (401,403,429):
                browser_url,browser_status=_site_browser_check(url,expected)
                if browser_url:return (browser_url,browser_status)
                return (url,"HTTP "+str(response.status_code)+" – "+browser_status)
        except _site_requests.RequestException:
            browser_url,browser_status=_site_browser_check(url,expected)
            if browser_url:return (browser_url,browser_status)
        return ("","")
''' + ui[end:]
# Avoid triggering browser twice on www and bare host when blocked; preserve fallback status.
ui=ui.replace('''if status.startswith("Erreichbar"):return (found,status)''','''if status.startswith("Erreichbar") or status.startswith("Browserzugriff"):return (found,status)''')
ui=ui.replace('''                st.write("Automatisch erreichbare Websites:",int(_site_df["Status"].astype(str).str.startswith("Erreichbar").sum()),"von",len(_site_df))''','''                st.write("Automatisch erreichbare Websites:",int(_site_df["Status"].astype(str).str.startswith(("Erreichbar","Browserzugriff")).sum()),"von",len(_site_df))''')
ui=ui.replace('''st.caption("HTTP 403/429: Die Adresse ist bekannt, der automatische Zugriff ist blockiert. Bitte im Browser prüfen.")''','''st.caption("Bei HTTP 403/429 versucht das Programm automatisch einen echten Browserzugriff. Auch Browser können vom Hersteller blockiert werden.")''')
ui=ui.replace('# Manufacturer website search v2.3.40','# Manufacturer website search v2.3.41')
ui=ui.replace('    try:\n        _site_conn=db()', '''    if st.button("Browserkomponente installieren",key="tga_browser_setup_241"):
        import subprocess as _site_subprocess
        import sys as _site_sys
        with st.spinner("Installiere Browserkomponente"):
            try:
                a=_site_subprocess.run([_site_sys.executable,"-m","pip","install","playwright"],capture_output=True,text=True,timeout=180)
                if a.returncode:st.error(a.stderr[-700:])
                else:
                    b=_site_subprocess.run([_site_sys.executable,"-m","playwright","install","chromium"],capture_output=True,text=True,timeout=240)
                    if b.returncode:st.error(b.stderr[-700:])
                    else:st.success("Browserkomponente installiert")
            except Exception as exc:st.error(str(exc))
    try:
        _site_conn=db()''')
s=prefix+ui
ast.parse(s)
p.write_text(s,encoding='utf-8')
v=root/'version.json';d=json.loads(v.read_text(encoding='utf-8'));d['version']='2.3.41';v.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
print("PASS browser fallback integrated")
