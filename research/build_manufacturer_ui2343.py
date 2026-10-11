"""Build v2.3.43: official manufacturer links in the user's normal browser.

Manual browser confirmation is stored separately from automatic HTTP reachability.
The phase is intentionally homepage-only: no product/article/document searching.
"""
import ast
import json
from pathlib import Path

root=Path("/tmp/tga2343")
app=root/"app.py"
s=app.read_text(encoding="utf-8")
assert 'APP_VERSION = "2.3.42"' in s
s=s.replace('APP_VERSION = "2.3.42"', 'APP_VERSION = "2.3.43"', 1)
old_marker="# Manufacturer website search v2.3.42"
assert s.count(old_marker)==1
s=s.replace(old_marker, "# Manufacturer website search v2.3.43", 1)
marker="# Manufacturer website search v2.3.43"
prefix=s[:s.index(marker)]
ui=s[s.index(marker):]

# Normal, user-operated browser links require no Playwright installation.
ui=ui.replace(
    '    st.caption("Phase 1: Hersteller-Startseiten; keine Produktseiten, Artikelnummern oder Dokumente.")',
    '''    st.caption("Phase 1: Hersteller-Startseiten; keine Produktseiten, Artikelnummern oder Dokumente.")
    st.info("Bei einer Cloudflare-Sperre die offizielle Website im normalen Browser öffnen. "
            "Nur eine tatsächlich geladene Herstellerseite manuell bestätigen; "
            "eine manuelle Bestätigung ist kein automatischer HTTP-Erfolg.")
    _browser_col1,_browser_col2=st.columns(2)
    with _browser_col1:
        st.link_button("WIKA im normalen Browser öffnen",
                       "https://www.wika.com/de-de/startseite.WIKA")
    with _browser_col2:
        st.link_button("Villeroy & Boch im normalen Browser öffnen",
                       "https://pro.villeroy-boch.com/de/de/home")''',1
)

# Correct official entry sources rather than trusting similarly named third-party domains.
ui=ui.replace(
    '        "wika":["https://www.wika.de/"],',
    '        "wika":["https://www.wika.com/de-de/startseite.WIKA","https://shop.wika.com/de-de/shop_startseite.WIKA"],',1
)
ui=ui.replace(
    '        "imi heimeier":["https://climatecontrol.imiplc.com/de-de"],',
    '        "imi heimeier":["https://climatecontrol.imiplc.com/de-de/frontpage-de"],',1
)
ui=ui.replace(
    '        "villeroy":["https://pro.villeroy-boch.com/de/de/home","https://pro.villeroy-boch.com/de/de/bad-und-wellness/service/downloads"],',
    '        "villeroy":["https://pro.villeroy-boch.com/de/de/home","https://www.villeroy-boch.de/"],',1
)

helpers='''    _site_manual_official={
        "wika":"https://www.wika.com/de-de/startseite.WIKA",
        "villeroy":"https://pro.villeroy-boch.com/de/de/home",
        "imi heimeier":"https://climatecontrol.imiplc.com/de-de/frontpage-de",
        "alape":"https://www.de.laufen.com/home",
        "witingsthal":"https://wittigsthal.de/",
        "wittingsthal":"https://wittigsthal.de/",
        "wittigsthal":"https://wittigsthal.de/"
    }
    def _site_manual_url(maker):
        """Approved manufacturer links only; no results from arbitrary search engines."""
        name=str(maker or "").casefold().strip()
        if not name:
            return ""
        for key,url in _site_manual_official.items():
            if key in name:
                return url
        known=next((domains for key,domains in _site_official.items() if key in name),[])
        if not known:
            return ""
        first=known[0]
        host=first.split("/")[0]
        suffix="/"+first.split("/",1)[1] if "/" in first else "/"
        return "https://www."+host+suffix
    def _site_auto_ok(status):
        """A blocked challenge or unreviewed redirect is never counted as success."""
        status=str(status or "")
        return status.endswith("Erreichbar – offizielle Domain") or status.endswith("Browserzugriff erfolgreich")
'''
needle="    def _site_find(session,maker):"
assert ui.count(needle)==1
ui=ui.replace(needle, helpers+needle,1)

# Prevent HTTP redirect to an unrelated domain from masquerading as a success.
needle='''                if status.startswith(("Erreichbar","Browserzugriff")):
                    return (found,source+" – "+status)'''
replacement='''                if _site_auto_ok(status):
                    return (found,source+" – "+status)'''
assert needle in ui
ui=ui.replace(needle,replacement,1)
needle='''                        if found:return (found,"Erreichbar – Herstellerzuordnung prüfen")'''
assert needle in ui
ui=ui.replace(needle,'''                        if found and _site_auto_ok(status):
                            return (found,"Erreichbar – Herstellerzuordnung prüfen")
                        # Discovery without confirmed maker ownership stays unverified.''',1)

# Block an HTTP-200 Cloudflare interstitial instead of declaring access success.
needle='''            if response.status_code<400 and len(response.content)>100:
                return (response.url,"Erreichbar – offizielle Domain" if allowed else "Erreichbar – Weiterleitung prüfen")'''
replacement='''            _site_challenge=any(token in response.text[:2500].casefold()
                                for token in ("just a moment", "cf-chl", "checking your browser",
                                              "verify you are human", "attention required! | cloudflare"))
            if response.status_code==200 and len(response.content)>100 and not _site_challenge:
                return (response.url,"Erreichbar – offizielle Domain" if allowed else "Erreichbar – Weiterleitung prüfen")'''
assert needle in ui
ui=ui.replace(needle,replacement,1)
needle='''                    if response is not None and response.status<400 and len(page.content())>100:'''
replacement='''                    if response is not None and response.status==200 and len(page.content())>100 and not any(
                            word in page.content()[:2500].casefold()
                            for word in ("just a moment", "cf-chl", "checking your browser", "verify you are human")):'''
assert needle in ui
ui=ui.replace(needle,replacement,1)

# The user's browser, not the server's headless browser, handles manual challenges.
# Human confirmation persists in the existing local project database with provenance.
needle='''            _site_project=st.selectbox("Projekt",_site_projects,key="tga_sites_project_239")'''
addition='''            _site_project=st.selectbox("Projekt",_site_projects,key="tga_sites_project_239")
            _site_conn.execute("""
                CREATE TABLE IF NOT EXISTS manufacturer_browser_verifications (
                    project TEXT NOT NULL,
                    manufacturer TEXT NOT NULL,
                    url TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    PRIMARY KEY (project, manufacturer)
                )
            """)
            _site_conn.commit()
            _site_manual_makers=[str(x[0] or "").strip() for x in
                _site_conn.execute("SELECT DISTINCT manufacturer FROM components WHERE project=? ORDER BY manufacturer",
                                   (_site_project,)).fetchall() if str(x[0] or "").strip()]
            if _site_manual_makers:
                st.markdown("#### Im normalen Browser überprüfen")
                _site_manual_maker=st.selectbox("Hersteller",_site_manual_makers,key="tga_manual_maker_243")
                _site_manual_link=_site_manual_url(_site_manual_maker)
                if _site_manual_link:
                    st.link_button("Herstellerwebsite im normalen Browser öffnen",_site_manual_link)
                    _site_db_confirm=_site_conn.execute(
                        "SELECT url,verified_at FROM manufacturer_browser_verifications "
                        "WHERE project=? AND manufacturer=?",
                        (_site_project,_site_manual_maker)).fetchone()
                    if _site_db_confirm:
                        st.success("Manuell bestätigt am "+str(_site_db_confirm[1])
                                   +" · Nicht als automatisch erreichbar gezählt.")
                        if st.button("Manuelle Bestätigung zurücknehmen",
                                     key="tga_site_unconfirm_243"):
                            _site_conn.execute(
                                "DELETE FROM manufacturer_browser_verifications "
                                "WHERE project=? AND manufacturer=?",
                                (_site_project,_site_manual_maker))
                            _site_conn.commit()
                            st.rerun()
                    else:
                        _site_ack=st.checkbox(
                            "Ich habe die echte Herstellerwebsite vollständig im Browser gesehen "
                            "(keine Cloudflare-Prüfseite).",
                            key="tga_site_ack_243_"+_site_project+"_"+_site_manual_maker)
                        if st.button("Browserzugriff manuell bestätigen",disabled=not _site_ack,
                                     key="tga_site_confirm_243"):
                            _site_conn.execute(
                                "INSERT OR REPLACE INTO manufacturer_browser_verifications "
                                "(project,manufacturer,url,verified_at) VALUES (?,?,?,datetime('now'))",
                                (_site_project,_site_manual_maker,_site_manual_link))
                            _site_conn.commit()
                            st.rerun()
                else:
                    st.warning("Für diesen Hersteller ist noch keine offiziell zugeordnete Website bekannt.")'''
assert needle in ui
ui=ui.replace(needle,addition,1)

# Keep separate machine and human status columns in the table and CSV.
needle='''                st.session_state["tga_sites_result_239"]=_site_df'''
replacement='''                _site_df["Browser-Link (manuell)"]=_site_df["Hersteller"].apply(_site_manual_url)
                _site_df["Automatisch erreichbar"]=_site_df["Status"].apply(_site_auto_ok)
                st.session_state["tga_sites_project_result_243"]=_site_project
                st.session_state["tga_sites_result_239"]=_site_df'''
assert needle in ui
ui=ui.replace(needle,replacement,1)
needle='''            if "tga_sites_result_239" in st.session_state:
                _site_df=st.session_state["tga_sites_result_239"]
                st.write("Automatisch erreichbare Websites:",int(_site_df["Status"].astype(str).str.contains("Erreichbar|Browserzugriff",regex=True).sum()),"von",len(_site_df))
                st.caption("Bei HTTP 403/429 versucht das Programm automatisch einen echten Browserzugriff. Auch Browser können vom Hersteller blockiert werden.")
                st.dataframe(_site_df,width="stretch",hide_index=True)'''
replacement='''            if ("tga_sites_result_239" in st.session_state and
                    st.session_state.get("tga_sites_project_result_243")==_site_project):
                _site_df=st.session_state["tga_sites_result_239"].copy()
                _site_verified={item[0] for item in _site_conn.execute(
                    "SELECT manufacturer FROM manufacturer_browser_verifications WHERE project=?",
                    (_site_project,)).fetchall()}
                _site_df["Manuell bestätigt"]=_site_df["Hersteller"].isin(_site_verified)
                st.write("Automatisch erreichbare Websites:",int(_site_df["Automatisch erreichbar"].sum()),"von",len(_site_df))
                st.write("Zusätzlich manuell bestätigt:",
                         int((_site_df["Manuell bestätigt"] & ~_site_df["Automatisch erreichbar"]).sum()))
                st.caption("HTTP 403/429: Bei automatischer Sperre die offizielle Adresse "
                           "mit dem eigenen Browser öffnen und das Ergebnis ausdrücklich bestätigen. "
                           "Manuelle und automatische Prüfung bleiben getrennt.")
                st.dataframe(_site_df,width="stretch",hide_index=True)'''
assert needle in ui
ui=ui.replace(needle,replacement,1)

s=prefix+ui
ast.parse(s)
app.write_text(s,encoding="utf-8")
version_file=root/"version.json"
version=json.loads(version_file.read_text(encoding="utf-8"))
assert version["version"]=="2.3.42"
version["version"]="2.3.43"
version_file.write_text(json.dumps(version,ensure_ascii=False,indent=2),encoding="utf-8")
print("PASS: v2.3.43 browser links, manual confirmations, and honest reachability statuses compiled")
