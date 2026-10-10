"""Patch v2.3.32 with opt-in private diagnosis uploader."""
import ast
import json
from pathlib import Path

root=Path("/tmp/tga2333")
app=root/"app.py"
s=app.read_text(encoding="utf-8")
assert 'APP_VERSION = "2.3.32"' in s
module=Path("research/private_diagnosis_upload.py").read_text(encoding="utf-8")
s=module+"\n"+s

# Controls live next to the article-research action, not in a global configuration panel.
anchor="    _bulk=[]"
assert anchor in s, "Bulk research block changed; refusing unsafe patch"
controls="""    st.markdown('##### Diagnoseberichte')
    _upload_enabled=st.checkbox('Diagnose-CSV nach der Recherche automatisch in das private GitHub-Repository hochladen',value=False,key='tga_private_diagnosis_enabled')
    _upload_token=''
    if _upload_enabled:
     _upload_token=st.text_input('GitHub-Zugriffstoken (nur für das private Diagnose-Repository)',type='password',key='tga_private_diagnosis_token',help='Fine-grained GitHub token: Repository TGA-Product-Finder-Diagnose, Contents: Read and write. Der Token wird nicht in CSV oder Programmdateien gespeichert.')
     st.caption('Die Diagnose enthält Projekt- und Produktdaten. Übertragung ausschließlich nach Aktivierung dieser Option.')
"""
# Add controls immediately before research starts, outside the button scope.
button_anchor="   if st.button('"
idx=s.find(button_anchor,s.find("def _tga_bulk_candidates"))
# Instead use the bulk list anchor, and persist the opt-in controls above the button.
bulk_start=s.index(anchor)
button_start=s.rfind("   if st.button(",0,bulk_start)
assert button_start>0
s=s[:button_start]+controls+s[button_start:]

needle="    st.session_state['bulk_article_results']=_bulk"
assert needle in s
upload="""    st.session_state['bulk_article_results']=_bulk
    try:
     _diag_path=save_diagnosis(_bulk,__import__('pathlib').Path.home()/'TGA_Product_Finder'/'Diagnose')
     st.session_state['tga_last_diagnosis_path']=str(_diag_path)
     if st.session_state.get('tga_private_diagnosis_enabled'):
      _token=st.session_state.get('tga_private_diagnosis_token','')
      if _token:
       _uploaded=upload_diagnosis(_diag_path,_token)
       st.success('Diagnose-CSV privat übertragen: '+_uploaded)
      else:
       st.warning('CSV lokal gespeichert. Für den privaten Upload fehlt das GitHub-Zugriffstoken.')
     else:
      st.info('Diagnose-CSV lokal gespeichert: '+str(_diag_path))
    except Exception as _diagnosis_error:
     st.warning('Diagnose-Upload/Speicherung: '+str(_diagnosis_error))
"""
s=s.replace(needle,upload,1)
s=s.replace('APP_VERSION = "2.3.32"','APP_VERSION = "2.3.33"',1)
ast.parse(s)
app.write_text(s,encoding="utf-8")
v=root/"version.json"
data=json.loads(v.read_text(encoding="utf-8"))
data["version"]="2.3.33"
v.write_text(json.dumps(data),encoding="utf-8")
print("PASS private diagnosis integration syntax")
