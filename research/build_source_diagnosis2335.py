import ast,json
from pathlib import Path
root=Path('/tmp/tga2335')
p=root/'app.py'
s=p.read_text(encoding='utf-8')
assert 'APP_VERSION = "2.3.34"' in s
s=Path('research/article_source_diagnosis.py').read_text(encoding='utf-8')+'\n'+s
start=s.index("     _hits,_err=_tga_bulk_candidates(",s.index("##### Diagnoseberichte"))
end=s.index("\n",start)
s=s[:start]+"""     _diag=_tga_diagnose_sources(_maker,_q,_model,_dimension)
     _hits=_diag['hits']
     _err=_diag['status']"""+s[end:]
needle="'Status':_status}"
assert needle in s
s=s.replace(needle,"'Status':_status,'Herstellerdomain':_diag['domain'] if _maker else '', 'Geprüfte URLs':', '.join(_diag['urls']) if _maker else '', 'Quellen-Diagnose':' | '.join(reason+' : '+url for url,reason in _diag['attempts']) if _maker else ''}",1)
# avoid stale _diag when manufacturer absent
s=s.replace("if not _maker:\n      _hits=[];_status=","if not _maker:\n      _diag={'domain':'','urls':[],'attempts':[]};_hits=[];_status=",1)
s=s.replace('APP_VERSION = "2.3.34"','APP_VERSION = "2.3.35"',1)
ast.parse(s)
p.write_text(s,encoding='utf-8')
v=root/'version.json';d=json.loads(v.read_text());d['version']='2.3.35';v.write_text(json.dumps(d))
print('PASS diagnostics integrated')
