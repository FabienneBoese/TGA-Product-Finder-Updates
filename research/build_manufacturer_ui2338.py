"""Repair website lookup with verified direct manufacturer host probes."""
from pathlib import Path
import ast,json
root=Path("/tmp/tga2338")
p=root/"app.py"
s=p.read_text(encoding="utf-8")
assert 'APP_VERSION = "2.3.37"' in s
s=s.replace('APP_VERSION = "2.3.37"','APP_VERSION = "2.3.38"',1)
start=s.index('# Manufacturer website research v2.3.37')
prefix=s[:start]
ui=s[start:]
needle='        candidates=[]\n'
assert needle in ui
replacement='''        # Known official manufacturer domains are probed directly before search engines.
        # Search-engine scraping is unreliable on hosted runners and must not be the sole source.
        known = {
            "helios":"heliosventilatoren.de","trox":"trox.de","lunos":"lunos.de",
            "rockwool":"rockwool.com","geberit":"geberit.de","grohe":"grohe.de",
            "viega":"viega.de","clage":"clage.de","alape":"alape.com",
            "wittingsthal":"wittingsthal.de","danfoss":"danfoss.com",
            "kermi":"kermi.com","grundfos":"grundfos.com","duravit":"duravit.de",
            "laufen":"laufen.com","hewi":"hewi.de","jung pumpen":"jung-pumpen.de",
            "viessmann":"viessmann.de","vaillant":"vaillant.de",
            "reflex":"reflex-winkelmann.com","wika":"wika.com",
            "imi heimeier":"imi-hydronic.com","ostendorf":"ostendorf-kunststoffe.com",
            "kemper":"kemper-group.com","villeroy":"villeroy-boch.de",
            "newo":"newo.de","herzbach":"herzbach.com",
            "emco":"emco-bath.com","schedel":"schedel-bad.de"}
        maker_key=maker.casefold()
        official=next((domain for name,domain in known.items() if name in maker_key),"")
        if official:
            for scheme in ("https://www.","https://"):
                try:
                    resp=session.get(scheme+official+"/",headers=_tga_headers,timeout=12,allow_redirects=True)
                    if resp.status_code < 400 and (
                        _tga_host(resp.url)==official or _tga_host(resp.url).endswith("."+official)):
                        return (resp.url,"","Offizielle Herstellerdomain; Website erreichbar","Herstellerwebsite bestätigt")
                except _tga_requests.RequestException:
                    pass
            return ("","","Bekannte Herstellerdomain nicht erreichbar","Herstellerwebsite nicht bestätigt")
        candidates=[]
'''
ui=ui.replace(needle,replacement,1)
# Focus phase 1 on websites and remove stale cache entries from old versions.
ui=ui.replace('herstellerdomains_cache.json','herstellerdomains_cache_v238.json')
ui=ui.replace('''"Produktseiten-URL":info[1],''','')
ui=ui.replace('''"Suchstatus":info[3]''','''"Suchstatus":info[3]''')
s=prefix+ui
ast.parse(s)
p.write_text(s,encoding="utf-8")
v=root/"version.json"
data=json.loads(v.read_text(encoding="utf-8"))
data["version"]="2.3.38"
v.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
print("PASS: direct official domain probing integrated")
