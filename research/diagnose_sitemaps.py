"""Investigate public manufacturer sitemap feasibility; read-only small sample."""
import requests,json,re
from urllib.parse import urlparse
from universal_product_search import maker_aliases,allowed_host
samples=[("TROX","https://www.trox.de"),
         ("Helios","https://www.heliosventilatoren.de"),
         ("WIKA","https://www.wika.com"),
         ("Geberit","https://www.geberit.de"),
         ("CLAGE GmbH","https://www.clage.de"),
         ("ROCKWOOL","https://www.rockwool.com")]
session=requests.Session()
for maker,base in samples:
    allowed=maker_aliases(maker)
    for path in ["/robots.txt","/sitemap.xml","/sitemap_index.xml"]:
        url=base+path
        try:
            r=session.get(url,timeout=(4,7),allow_redirects=True,headers={"User-Agent":"TGA-Product-Finder sitemap discovery"})
            lines=r.text[:5000].splitlines()
            sitemaps=[x.strip() for x in lines if x.lower().strip().startswith("sitemap:")]
            tags=re.findall(r"<loc>\s*([^<]+)\s*</loc>",r.text[:250000],re.I)
            print("SITEMAP_DIAG",json.dumps(dict(maker=maker,path=path,status=r.status_code,
              url=r.url,allowed=allowed_host(r.url,allowed),type=r.headers.get("Content-Type",""),
              size=len(r.content),sitemaps=sitemaps[:5],first_urls=tags[:6],
              blocked=("just a moment" in r.text[:3000].lower())),ensure_ascii=False),flush=True)
        except requests.RequestException as exc:
            print("SITEMAP_DIAG",maker,path,type(exc).__name__,flush=True)
