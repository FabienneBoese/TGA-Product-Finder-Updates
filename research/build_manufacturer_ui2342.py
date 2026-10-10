from pathlib import Path
import ast,json
p=Path('/tmp/tga2342/app.py')
s=p.read_text(encoding='utf-8')
assert 'APP_VERSION = "2.3.41"' in s
s=s.replace('APP_VERSION = "2.3.41"','APP_VERSION = "2.3.42"',1)
marker='# Manufacturer website search v2.3.41'
assert marker in s
s=s.replace(marker,'# Manufacturer website search v2.3.42',1)
needle='    def _site_find(session,maker):'
assert needle in s
insertion='''    _site_channels={
        "villeroy":["https://pro.villeroy-boch.com/de/de/home","https://pro.villeroy-boch.com/de/de/bad-und-wellness/service/downloads"],
        "wika":["https://www.wika.de/"],
        "duravit":["https://www.duravit.com/"],
        "grohe":["https://www.grohe.com/de/"],
        "alape":["https://www.laufen.com/vitreon-steel"],
        "imi heimeier":["https://climatecontrol.imiplc.com/de-de"],
        "rockwool":["https://www.rockwool.com/de/"],
        "emco":["https://www.emco-bath.com/de/"],
        "schedel":["https://schedel-badinnovation.de/"]
    }
'''
s=s.replace(needle,insertion+needle,1)
start=s.index(needle);end=s.index('    if st.button("Browserkomponente installieren"',start)
section=s[start:end]
needle2='''        for domain in known:
            for prefix in ("https://www.","https://"):
                host=domain.split("/")[0]
                path="/"+domain.split("/",1)[1] if "/" in domain else "/"
                found,status=_site_check(session,prefix+host+path,host)
                if found:
                    if status.startswith("Erreichbar") or status.startswith("Browserzugriff"):return (found,status)
                    if blocked is None:blocked=(found,status)
        if blocked is not None:return blocked'''
assert needle2 in section
replacement='''        channels=next((urls for key,urls in _site_channels.items() if key in name),[])
        candidates=[("Fachportal",url) for url in channels]
        for domain in known:
            host=domain.split("/")[0]
            path="/"+domain.split("/",1)[1] if "/" in domain else "/"
            candidates.extend(("Herstellerwebsite",prefix+host+path) for prefix in ("https://www.","https://"))
        for source,url in dict.fromkeys(candidates):
            found,status=_site_check(session,url,_site_host(url))
            if found:
                if status.startswith(("Erreichbar","Browserzugriff")):
                    return (found,source+" – "+status)
                if blocked is None:blocked=(found,status)
        if blocked is not None:return blocked'''
section=section.replace(needle2,replacement)
s=s[:start]+section+s[end:]
s=s.replace('''_site_df["Status"].astype(str).str.startswith(("Erreichbar","Browserzugriff"))''','''_site_df["Status"].astype(str).str.contains("Erreichbar|Browserzugriff",regex=True)''')
ast.parse(s)
p.write_text(s,encoding='utf-8')
v=Path('/tmp/tga2342/version.json');d=json.loads(v.read_text(encoding='utf-8'));d['version']='2.3.42';v.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
print('PASS')
