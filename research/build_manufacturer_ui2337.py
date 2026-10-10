"""Build self-contained v2.3.37, compatible with app.py-only updater."""
from pathlib import Path
import ast,json
root=Path("/tmp/tga2337")
p=root/"app.py"
s=p.read_text(encoding="utf-8")
assert 'APP_VERSION = "2.3.36"' in s
s=s.replace('APP_VERSION = "2.3.36"','APP_VERSION = "2.3.37"',1)
marker='# Manufacturer website and product-page research (v2.3.36)'
assert marker in s
s=s.split(marker)[0]
ui='''
# Manufacturer website research v2.3.37 - self-contained for existing updater
with st.expander("🌐 Herstellerwebsites und Produktseiten automatisch suchen"):
    st.caption("Phase 1: Herstellerwebsites und Produktseiten, keine Artikelnummern oder PDFs.")
    import requests as _tga_requests
    import re as _tga_re
    import json as _tga_json
    import pandas as _tga_pd
    from pathlib import Path as _tga_Path
    from urllib.parse import urlparse as _tga_urlparse, parse_qs as _tga_qs, unquote as _tga_unquote
    from bs4 import BeautifulSoup as _tga_Soup
    _tga_headers = {"User-Agent":"Mozilla/5.0"}
    def _tga_host(url):
        return (_tga_urlparse(url).hostname or "").lower().removeprefix("www.")
    def _tga_tokens(value):
        return [t for t in _tga_re.findall(r"[a-z0-9]+",str(value or "").casefold()) if len(t)>=3]
    def _tga_discover(session,maker,product,model):
        maker=str(maker or "").strip()
        if not maker:return ("","","","Hersteller fehlt")
        candidates=[]
        for endpoint,params in (("https://www.bing.com/search",{"q":maker+" offizielle Hersteller Website"}),
                                ("https://www.bing.com/search",{"q":maker+" Hersteller","format":"rss"}),
                                ("https://html.duckduckgo.com/html/",{"q":maker+" offizielle Website"})):
            try:
                response=session.get(endpoint,params=params,headers=_tga_headers,timeout=7)
                if response.status_code!=200:continue
                soup=_tga_Soup(response.text,"html.parser")
                for a in soup.select("a[href], item link"):
                    href=a.get("href") or a.get_text(strip=True)
                    if "uddg=" in href:href=_tga_qs(_tga_urlparse(href).query).get("uddg",[href])[0]
                    if href.startswith("/url?"):href=_tga_qs(_tga_urlparse(href).query).get("q",[""])[0]
                    href=_tga_unquote(href)
                    host=_tga_host(href)
                    if href.startswith("https://") and host and not any(x in host for x in ("amazon.","ebay.","wikipedia.","linkedin.","facebook.","youtube.","idealo.")):
                        candidates.append(href)
            except _tga_requests.RequestException:pass
        keytokens=[t for t in _tga_tokens(maker) if t not in ("gmbh","technik","group","deutschland")]
        website=""
        domain=""
        status="Keine Herstellerwebsite bestätigt"
        for candidate in candidates:
            host=_tga_host(candidate)
            hostflat=_tga_re.sub("[^a-z0-9]","",host.split(".")[0])
            if not keytokens or not any(t in hostflat for t in keytokens):continue
            try:
                home=session.get("https://"+host+"/",headers=_tga_headers,timeout=8)
                if home.status_code==200 and _tga_host(home.url)==host:
                    domain=host
                    website=home.url
                    status="Website erreichbar; Herstellerzuordnung prüfen"
                    break
            except _tga_requests.RequestException:pass
        if not domain:return ("","",status,"Keine Produktseite gefunden")
        producturl=""
        searchquery="site:"+domain+" "+str(product or "")+" "+str(model or "")
        try:
            result=session.get("https://www.bing.com/search",params={"q":searchquery},headers=_tga_headers,timeout=10)
            if result.status_code==200:
                soup=_tga_Soup(result.text,"html.parser")
                for a in soup.select("a[href]"):
                    link=a.get("href","")
                    if not link.startswith("https://") or _tga_host(link)!=domain:continue
                    path=_tga_urlparse(link).path.casefold()
                    if path in ("","/") or path.endswith(".pdf"):continue
                    title=a.get_text(" ",strip=True).casefold()
                    tokens=_tga_tokens(model) or _tga_tokens(product)
                    if tokens and any(t in path or t in title for t in tokens):
                        producturl=link
                        break
        except _tga_requests.RequestException:pass
        return (website,producturl,status,"Produktseiten-Kandidat (Prüfung erforderlich)" if producturl else "Produktseite nicht bestätigt")
    try:
        _tga_conn=db()
        _tga_projects=[r[0] for r in _tga_conn.execute("SELECT DISTINCT project FROM components WHERE project IS NOT NULL ORDER BY project").fetchall()]
        if _tga_projects:
            _tga_project=st.selectbox("Projekt für Herstellerrecherche",_tga_projects,key="tga_site_project_v237")
            if st.button("Herstellerwebsites und Produktseiten suchen",key="tga_site_search_v237"):
                _tga_items=_tga_conn.execute("SELECT manufacturer,product,model_type FROM components WHERE project=?",(_tga_project,)).fetchall()
                _tga_cache_path=_tga_Path(__file__).resolve().parent/"herstellerdomains_cache.json"
                try:_tga_cache=_tga_json.loads(_tga_cache_path.read_text(encoding="utf-8"))
                except (OSError,ValueError):_tga_cache={}
                _tga_output=[]
                with st.spinner("Herstellerwebsites werden gesucht ..."):
                    with _tga_requests.Session() as _tga_session:
                        for maker,product,model in _tga_items:
                            key=str(maker or "").casefold().strip()
                            info=_tga_cache.get(key)
                            if not info:
                                info=_tga_discover(_tga_session,maker,product,model)
                                if info[0]:_tga_cache[key]=info
                            _tga_output.append({"Hersteller":maker,"Produkt":product,"Typ / Modell":model,
                                                "Herstellerwebsite":info[0],"Produktseiten-URL":info[1],
                                                "Herstellerwebsite-Status":info[2],"Suchstatus":info[3]})
                _tga_cache_path.write_text(_tga_json.dumps(_tga_cache,ensure_ascii=False,indent=2),encoding="utf-8")
                st.session_state["tga_sites_v237"]=_tga_pd.DataFrame(_tga_output)
            if "tga_sites_v237" in st.session_state:
                _tga_df=st.session_state["tga_sites_v237"]
                st.dataframe(_tga_df,width="stretch",hide_index=True)
                st.download_button("Ergebnisse als CSV herunterladen",_tga_df.to_csv(sep=";",index=False).encode("utf-8-sig"),"TGA_Herstellerseiten.csv","text/csv")
        else:st.info("Noch keine Komponenten vorhanden.")
        _tga_conn.close()
    except Exception as _tga_exc:
        st.error("Herstellerrecherche: "+str(_tga_exc))
'''
s+=ui
ast.parse(s)
p.write_text(s,encoding="utf-8")
v=root/"version.json"
data=json.loads(v.read_text(encoding="utf-8"))
data["version"]="2.3.37"
v.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
print("PASS: standalone manufacturer search integrated")
