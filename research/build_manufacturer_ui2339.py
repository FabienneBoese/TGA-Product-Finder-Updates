"""Build v2.3.39: exhaustive manufacturer-homepage probing and honest status."""
from pathlib import Path
import ast,json
root=Path("/tmp/tga2339")
p=root/"app.py"
s=p.read_text(encoding="utf-8")
assert 'APP_VERSION = "2.3.38"' in s
s=s.replace('APP_VERSION = "2.3.38"','APP_VERSION = "2.3.39"',1)
marker='# Manufacturer website research v2.3.37'
assert marker in s
s=s[:s.index(marker)]
ui='''
# Manufacturer website search v2.3.39
with st.expander("🌐 Herstellerwebsites automatisch finden und prüfen"):
    st.caption("Phase 1: Hersteller-Startseiten; keine Produktseiten, Artikelnummern oder Dokumente.")
    import requests as _site_requests
    import pandas as _site_pd
    import re as _site_re
    import json as _site_json
    from pathlib import Path as _site_Path
    from urllib.parse import urlparse as _site_parse,parse_qs as _site_qs,unquote as _site_unquote
    from bs4 import BeautifulSoup as _site_soup
    _site_official={
      "helios":["heliosventilatoren.de"],"trox":["trox.de"],"lunos":["lunos.de"],
      "danfoss":["danfoss.com"],"reflex":["reflex-winkelmann.com"],"wika":["wika.com"],
      "viega":["viega.de"],"imi heimeier":["imi-hydronic.com"],"rockwool":["rockwool.com"],
      "kermi":["kermi.com"],"ostendorf":["ostendorf-kunststoffe.com"],
      "jung pumpen":["jung-pumpen.de"],"kemper":["kemper-group.com","kemper-group.de"],
      "geberit":["geberit.de"],"villeroy":["villeroy-boch.de","villeroy-boch.com"],
      "newo":["newo.de"],"duravit":["duravit.de"],"herzbach":["herzbach.com"],
      "emco":["emco-bath.com"],"schedel":["schedel-bad.de"],"laufen":["laufen.com"],
      "hewi":["hewi.de"],"alape":["alape.com"],"witingsthal":["wittingsthal.de"],
      "wittingsthal":["wittingsthal.de"],"clage":["clage.de"],
      "grohe":["grohe.de","grohe.com"],"grundfos":["grundfos.com"],
      "viessmann":["viessmann.de"],"vaillant":["vaillant.de"],
      "villeroy & boch":["villeroy-boch.de","villeroy-boch.com"]}
    def _site_host(url):
        return (_site_parse(url).hostname or "").lower().removeprefix("www.")
    def _site_check(session,url,expected):
        try:
            response=session.get(url,timeout=9,allow_redirects=True,headers={"User-Agent":"Mozilla/5.0"})
            host=_site_host(response.url)
            allowed=(host==expected or host.endswith("."+expected))
            # A vendor can redirect its official domain to another locale/domain.
            if response.status_code<400 and len(response.content)>100:
                return (response.url,"Erreichbar – offizielle Domain" if allowed else "Erreichbar – Weiterleitung prüfen")
        except _site_requests.RequestException:pass
        return ("","")
    def _site_find(session,maker):
        maker=str(maker or "").strip()
        if not maker:return ("","Herstellerangabe fehlt")
        name=maker.casefold()
        known=next((domains for key,domains in _site_official.items() if key in name),[])
        for domain in known:
            for prefix in ("https://www.","https://"):
                found,status=_site_check(session,prefix+domain+"/",domain)
                if found:return (found,status)
        # Unknown manufacturers: try search results, verify HTTP and brand-name host.
        if not known:
            brand=_site_re.sub("[^a-z0-9]","",_site_re.split(r"\\s+|/",name)[0])
            for engine,params in (
                ("https://www.bing.com/search",{"q":maker+" offizielle Website","format":"rss"}),
                ("https://html.duckduckgo.com/html/",{"q":maker+" Hersteller Website"})):
                try:
                    response=session.get(engine,params=params,timeout=9,headers={"User-Agent":"Mozilla/5.0"})
                    if response.status_code!=200:continue
                    soup=_site_soup(response.text,"html.parser")
                    links=[x.get("href","") for x in soup.select("a[href]")]
                    links += [x.get_text(strip=True) for x in soup.find_all("link")]
                    for href in links[:40]:
                        if "uddg=" in href:href=_site_qs(_site_parse(href).query).get("uddg",[""])[0]
                        href=_site_unquote(href)
                        host=_site_host(href)
                        if not href.startswith("https://") or not host:continue
                        if any(x in host for x in ("bing.","duckduckgo.","google.","amazon.","wikipedia.","linkedin.")):continue
                        if len(brand)<4 or brand not in _site_re.sub("[^a-z0-9]","",host):continue
                        found,status=_site_check(session,href,host)
                        if found:return (found,"Erreichbar – Herstellerzuordnung prüfen")
                except _site_requests.RequestException:pass
        return ("","Nicht erreichbar / nicht bestätigt" if known else "Keine Herstellerwebsite bestätigt")
    try:
        _site_conn=db()
        _site_projects=[x[0] for x in _site_conn.execute("SELECT DISTINCT project FROM components WHERE project IS NOT NULL ORDER BY project").fetchall()]
        if _site_projects:
            _site_project=st.selectbox("Projekt",_site_projects,key="tga_sites_project_239")
            if st.button("Alle Herstellerwebsites prüfen",key="tga_sites_run_239"):
                _site_rows=_site_conn.execute("SELECT manufacturer,product FROM components WHERE project=?",(_site_project,)).fetchall()
                _site_makers=list(dict.fromkeys(str(x[0] or "").strip() for x in _site_rows))
                _site_results={}
                _site_progress=st.progress(0)
                with _site_requests.Session() as _site_session:
                    for index,maker in enumerate(_site_makers):
                        url,status=_site_find(_site_session,maker)
                        _site_results[maker]=(url,status)
                        _site_progress.progress((index+1)/max(1,len(_site_makers)))
                _site_df=_site_pd.DataFrame([{"Hersteller":maker,"Herstellerwebsite":_site_results[maker][0],
                                              "Status":_site_results[maker][1],
                                              "Anzahl Produkte":sum(1 for x in _site_rows if str(x[0] or "").strip()==maker)}
                                             for maker in _site_makers])
                st.session_state["tga_sites_result_239"]=_site_df
            if "tga_sites_result_239" in st.session_state:
                _site_df=st.session_state["tga_sites_result_239"]
                st.write("Erreichbare Websites:",int(_site_df["Herstellerwebsite"].astype(bool).sum()),"von",len(_site_df))
                st.dataframe(_site_df,width="stretch",hide_index=True)
                st.download_button("Ergebnisse als CSV",_site_df.to_csv(index=False,sep=";").encode("utf-8-sig"),"TGA_Herstellerwebsites.csv","text/csv",key="tga_sites_export_239")
        _site_conn.close()
    except Exception as _site_exc:
        st.error("Herstellerseitensuche: "+str(_site_exc))
'''
s+=ui
ast.parse(s)
p.write_text(s,encoding="utf-8")
v=root/"version.json"
data=json.loads(v.read_text(encoding="utf-8"));data["version"]="2.3.39"
v.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
print("PASS manufacturer-only app integration")
