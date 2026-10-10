"""Build v2.3.36: integrate manufacturer website discovery into Streamlit app."""
from pathlib import Path
import ast, json, shutil

root = Path("/tmp/tga2336")
app = root / "app.py"
source = app.read_text(encoding="utf-8")
assert 'APP_VERSION = "2.3.35"' in source
source = source.replace('APP_VERSION = "2.3.35"', 'APP_VERSION = "2.3.36"', 1)
module_dir = root / "research"
module_dir.mkdir(exist_ok=True)
for name in ("manufacturer_domain_resolver.py", "manufacturer_page_finder.py",
             "headless_article_research.py", "manufacturer_article_engine.py"):
    shutil.copy2(Path("research") / name, module_dir / name)

ui = '''
# Manufacturer website and product-page research (v2.3.36)
import sys as _tga_sys
from pathlib import Path as _tga_Path
_tga_research_path = str(_tga_Path(__file__).resolve().parent / "research")
if _tga_research_path not in _tga_sys.path:
    _tga_sys.path.insert(0, _tga_research_path)

with st.expander("🌐 Herstellerwebsites und Produktseiten automatisch suchen", expanded=False):
    st.caption("Phase 1: offizielle Herstellerwebsite ermitteln, danach passende Produktseite suchen. Keine Artikelnummern- oder Dokumentensuche.")
    try:
        _tga_connection = db()
        _tga_projects = [r[0] for r in _tga_connection.execute(
            "SELECT DISTINCT project FROM components WHERE project IS NOT NULL ORDER BY project").fetchall()]
        if _tga_projects:
            _tga_project = st.selectbox("Projekt für Herstellerrecherche", _tga_projects, key="tga_web_project")
            if st.button("Herstellerwebsites und Produktseiten suchen", key="tga_web_research"):
                import requests as _tga_requests
                import pandas as _tga_pd
                from manufacturer_domain_resolver import resolve as _tga_resolve, load_cache as _tga_load, save_cache as _tga_save
                from manufacturer_page_finder import classify as _tga_classify
                _tga_rows = _tga_connection.execute(
                    "SELECT manufacturer,product,model_type FROM components WHERE project=?", (_tga_project,)).fetchall()
                _tga_cache_file = _tga_Path(__file__).resolve().parent / "herstellerdomains_cache.json"
                _tga_cache = _tga_load(_tga_cache_file)
                _tga_info = {}
                _tga_results = []
                from headless_article_research import domain_for as _tga_known_domain
                with st.spinner("Offizielle Herstellerwebsites und Produktseiten werden gesucht ..."):
                    with _tga_requests.Session() as _tga_session:
                        for _tga_maker, _tga_product, _tga_model in _tga_rows:
                            _tga_key = str(_tga_maker or "").casefold().strip()
                            if _tga_key not in _tga_info:
                                _tga_info[_tga_key] = _tga_resolve(_tga_session, _tga_maker, _tga_cache, _tga_known_domain(_tga_maker))
                            _tga_results.append(_tga_classify(_tga_session, {
                                "Hersteller": _tga_maker or "", "Produkt": _tga_product or "",
                                "Typ / Modell": _tga_model or ""}, _tga_info[_tga_key]))
                _tga_save(_tga_cache_file, _tga_cache)
                st.session_state["tga_web_results"] = _tga_pd.DataFrame(_tga_results)
            if "tga_web_results" in st.session_state:
                _tga_frame = st.session_state["tga_web_results"]
                _tga_columns = ["Hersteller", "Produkt", "Typ / Modell", "Herstellerwebsite",
                                "Herstellerwebsite-Status", "Produktseiten-URL", "Suchstatus"]
                st.dataframe(_tga_frame[[c for c in _tga_columns if c in _tga_frame.columns]],
                             width="stretch", hide_index=True)
                st.download_button("Ergebnisse als CSV herunterladen",
                    _tga_frame.to_csv(index=False, sep=";").encode("utf-8-sig"),
                    "TGA_Herstellerwebsites_und_Produktseiten.csv", "text/csv", key="tga_web_download")
        else:
            st.info("Noch keine Komponenten im Projekt vorhanden.")
        _tga_connection.close()
    except Exception as _tga_error:
        st.warning("Herstellerrecherche derzeit nicht verfügbar: " + str(_tga_error))
'''
source += "\n" + ui
ast.parse(source)
app.write_text(source, encoding="utf-8")
version = root / "version.json"
data = json.loads(version.read_text(encoding="utf-8"))
data["version"] = "2.3.36"
version.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("Manufacturer research integrated in app v2.3.36")
