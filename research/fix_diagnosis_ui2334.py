"""Repair visibility of diagnosis upload controls, validate actual app placement."""
import ast,re,json
from pathlib import Path
root=Path('/tmp/tga2334')
p=root/'app.py'
s=p.read_text(encoding='utf-8')
assert 'APP_VERSION = "2.3.33"' in s
start=s.index("   st.markdown('##### Diagnoseberichte')")
end=s.index("    st.caption('Die Diagnose enthält Projekt- und Produktdaten. Übertragung ausschließlich nach Aktivierung dieser Option.')",start)+len("    st.caption('Die Diagnose enthält Projekt- und Produktdaten. Übertragung ausschließlich nach Aktivierung dieser Option.')")
controls=s[start:end]
s=s[:start]+s[end:]
# Anchor by the exact visible button, not the nearest unrelated st.button.
matches=list(re.finditer(r"(?m)^([ \t]*)if st\.button\(['\"]Artikelnummern aller Komponenten automatisch recherchieren",s))
assert len(matches)==1, 'Expected exactly one bulk article research button, got '+str(len(matches))
m=matches[0]
indent=m.group(1)
controls='\n'.join(indent+line[3:] if line.startswith('   ') else line for line in controls.split('\n'))
s=s[:m.start()]+controls+'\n'+s[m.start():]
assert s.index("##### Diagnoseberichte")<s.index("Artikelnummern aller Komponenten automatisch recherchieren")
# UI controls and button share exact same indentation.
assert re.search(r"(?m)^"+re.escape(indent)+r"_upload_enabled=st\.checkbox\('Diagnose-CSV",s)
assert re.search(r"(?m)^"+re.escape(indent)+r"if st\.button\('Artikelnummern aller Komponenten",s)
s=s.replace('APP_VERSION = "2.3.33"','APP_VERSION = "2.3.34"',1)
ast.parse(s)
p.write_text(s,encoding='utf-8')
v=root/'version.json'
data=json.loads(v.read_text());data['version']='2.3.34';v.write_text(json.dumps(data))
print('PASS upload checkbox positioned immediately before visible bulk button')
