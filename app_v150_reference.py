import os
import tempfile
import time
import hashlib
import json
from pathlib import Path
import io, re, sqlite3, urllib.parse, os, hashlib
from urllib.parse import urljoin, urlparse
import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st

# Dauerhafte Benutzerdaten liegen getrennt von den Programmdateien.
DATA_ROOT = os.environ.get('TGA_DATA_DIR') or os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'TGA Product Finder', 'Data')
os.makedirs(DATA_ROOT, exist_ok=True)
DB = os.path.join(DATA_ROOT, 'tga_finder.db')
DOWNLOAD_ROOT = os.path.join(DATA_ROOT, 'offline_dokumente')
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)
DOMAINS={'trox':'trox.de','rockwool':'rockwool.com','grohe':'grohe.de','geberit':'geberit.de'}
PRODUCTS={
 ('trox','FK2-EU'):[
  'https://www.trox.de/brandschutzklappen/fk2-eu-d43c8f48f846955c',
  'https://www.trox.de/brand--und-rauchschutzsysteme/die-neue-brandschutzklappe-fk2-eu-02dbf47edadaf2f1',
 ],
 ('trox','TVE'):[
  'https://www.trox.de/vvs-regelgeraete/tve-3fb25f4ac74c6313',
 ],
 ('rockwool','800'):[
  'https://www.rockwool.com/de/produkte/rockwool-800/',
 ],
 ('rockwool','CONLIT U'):[
  'https://www.rockwool.com/de/produkte/conlit-150-u/',
  'https://dxp.rockwool.com/de/anwendungen/produktuebersicht/conlit-150-u/',
 ],
 ('rockwool','CONLIT 150 U'):[
  'https://www.rockwool.com/de/produkte/conlit-150-u/',
  'https://dxp.rockwool.com/de/anwendungen/produktuebersicht/conlit-150-u/',
 ],
}

ROCKWOOL_SPECIAL_SOURCES={
 'certificates':'https://www.rockwool.com/de/downloads-und-services/downloads/zertifikate/',
 'blue_angel':'https://www.rockwool.com/de/rat-und-tat/vertiefendes-wissen/umweltschutz-und-wohngesundheit/blauer-engel/',
}
ROCKWOOL_DOP_IDS={'800':'DE0721042201'}
ROCKWOOL_PRODUCT_PROOFS={'CONLIT U':'P-NDS04-417'}
ROCKWOOL_DIRECT_CERTIFICATES={
 '800':{
  'eurofins':'https://brandcommunity.rockwool.com/asset/ZxK0dbkv_tyZ8qJtpG6NVw/asset.pdf?quality=10',
  'blue_angel_registry':'https://www.blauer-engel.de/de/produkte/rockwool-daemmstoffe-fuer-technische-gebaeudeausruestung-gemaess-din-en-14303-rockwool-800-conlit-150u',
 },
 'CONLIT U':{
  'eurofins_page':'https://www.rockwool.com/de/downloads-und-services/downloads/zertifikate/',
  'eurofins_title':'Zertifikat Conlit 150 U Indoor Air Comfort Gold',
  'blue_angel_registry':'https://www.blauer-engel.de/de/produkte/rockwool-daemmstoffe-fuer-technische-gebaeudeausruestung-gemaess-din-en-14303-rockwool-800-conlit-150u',
 }
}



GROHE_VERIFIED_DOCS={
 '36327001':[
  {'Kategorie':'Produktdatenblatt','Priorität':'Empfohlen','Titel':'GROHE Product Datasheet 36327001','URL':'https://www.grohe.co.za/getmodule.php?id=pdf_generator.php&stock_code=GRO-G-36271000','Resolver':'GROHE verifizierter Online-Nachweis','Downloadbar':False,'Nachweis URL':'https://www.grohe.co.za/getmodule.php?id=pdf_generator.php&stock_code=GRO-G-36271000'},
  {'Kategorie':'Zulassung / Prüfzeugnis','Priorität':'Optional','Titel':'P-IX Prüfzeichen – PA-IX 16756/IO','URL':'https://cdn.cloud.grohe.com/Web/local_PDF/de_DE/P-IX_Pruefzeichen/original/P-IX_Pruefzeichen.pdf','Resolver':'GROHE Prüfzeichenregister · artikelbezogen verifiziert','Downloadbar':False,'Nachweis URL':'https://cdn.cloud.grohe.com/Web/local_PDF/de_DE/P-IX_Pruefzeichen/original/P-IX_Pruefzeichen.pdf'},
  {'Kategorie':'Broschüre / Planung','Priorität':'Optional','Titel':'GROHE Projekt 2024 – 36327001','URL':'https://cdn.cloud.grohe.com/Literature/Brochures/dk_DK/grohe_2024_DK_brochure_projekt_v2_LOW/original/grohe_2024_DK_brochure_projekt_v2_LOW.pdf','Resolver':'GROHE Projektunterlage'},
 ]
}


GEBERIT_VERIFIED_PRODUCTS={
 '501.632.00.1':{
  'name':'Geberit Renova Plan Waschtisch',
  'details':'55 cm · weiß · Hahnloch mittig · mit Überlauf',
  'page':'https://catalog.geberit.de/de-DE/product/PRO_1737077',
  'docs':[
   {'Kategorie':'Produktdatenblatt','Priorität':'Empfohlen','Titel':'Geberit Renova Plan – Produktdatenblatt 501.632.00.1','URL':'https://catalog.geberit.de/de-DE/product/PRO_1737077','Resolver':'Geberit Produktkatalog · verifizierter Online-Nachweis','Downloadbar':False,'Nachweis URL':'https://catalog.geberit.de/de-DE/product/PRO_1737077'},
  ]
 }
}


MAPRESS_THERM_GROUPS={
 'Systemrohr CrTi':{'details':'CrTi-Stahl 1.4520 · DN 12–100 · d15–108 mm','page':'https://catalog.geberit.de/de-DE/product/PRO_3207998'},
 'Fitting / Formstück':{'details':'Pressfittings · Dokumentgruppe wird nach Bauform gewählt; Dimension ist für die Dokumentmappe nicht erforderlich','page':'https://www.geberit.de/sanitaer-rohrleitungssysteme/versorgungssysteme/geberit-mapress/geberit-mapress-therm/'},
}

MAPRESS_THERM_FITTINGS={
 'Muffe':{
  'page':'https://catalog.geberit.de/de-DE/product/PRO_3207533',
  'docs':[
   {'Kategorie':'Produktdatenblatt','Priorität':'Empfohlen','Titel':'Geberit Mapress Therm Muffe – Produktdatenblatt','Resolver':'Geberit Produktkatalog · verifizierter Online-Nachweis'},
   {'Kategorie':'EPD / DGNB / Umwelt','Priorität':'Empfohlen','Titel':'Geberit Mapress Therm Muffe – Umweltproduktdeklaration','Resolver':'Geberit Produktkatalog · EPD-Nachweis'},
  ],
  'variants':{
   'd15 / DN12':'44002','d18 / DN15':'44003','d22 / DN20':'44004','d28 / DN25':'44005','d35 / DN32':'44006',
   'd42 / DN40':'44007','d54 / DN50':'44008','d76,1 / DN65':'44009','d88,9 / DN80':'44010','d108 / DN100':'44011',
  }
 },
 'Schiebemuffe':{
  'page':'https://catalog.geberit.de/de-DE/product/PRO_3207553',
  'docs':[
   {'Kategorie':'Produktdatenblatt','Priorität':'Empfohlen','Titel':'Geberit Mapress Therm Schiebemuffe – Produktdatenblatt','Resolver':'Geberit Produktkatalog · verifizierter Online-Nachweis'},
   {'Kategorie':'EPD / DGNB / Umwelt','Priorität':'Empfohlen','Titel':'Geberit Mapress Therm Schiebemuffe – Umweltproduktdeklaration','Resolver':'Geberit Produktkatalog · EPD-Nachweis'},
  ],
  'variants':{
   'd15 / DN12':'42102','d18 / DN15':'42103','d22 / DN20':'42104','d28 / DN25':'42105','d35 / DN32':'42106',
   'd42 / DN40':'42107','d54 / DN50':'42108','d76,1 / DN65':'42109','d88,9 / DN80':'42110','d108 / DN100':'42111',
  }
 },
}

def is_geberit_mapress_therm(manufacturer, product):
 return 'geberit' in clean(manufacturer).lower() and 'MAPRESS THERM' in clean(product).upper()

def mapress_group_label(group):
 v=MAPRESS_THERM_GROUPS[group]
 return f"{group} — {v['details']}"

def is_geberit_verified(manufacturer, article):
 return 'geberit' in clean(manufacturer).lower() and clean(article) in GEBERIT_VERIFIED_PRODUCTS

def find_geberit_docs(article):
 article=clean(article)
 cfg=GEBERIT_VERIFIED_PRODUCTS.get(article)
 if not cfg: raise ValueError('Diese Geberit-Artikelnummer ist in v0.6.0 noch nicht automatisch freigeschaltet.')
 docs=[]
 for d in cfg['docs']:
  row=dict(d); row.update({'Treffer %':100,'Quellseite':cfg['page'],'Relevant':True}); row.setdefault('Nachweis URL',''); docs.append(row)
 return cfg['page'],docs

GROHE_VARIANTS={
 '36324001':{'name':'Eurosmart CE · Waschtisch · Niederdruck','details':'Niederdruck / offener Warmwasserbereiter · Netzbetrieb · mit Mischung'},
 '36325001':{'name':'Eurosmart CE · Waschtisch · Netzbetrieb','details':'Hochdruck · Steckertrafo 100–240 V · Sensor · mit Mischung'},
 '36327001':{'name':'Eurosmart CE · Waschtisch · Batteriebetrieb','details':'Hochdruck · 6-V-Batterie · Sensor · mit Mischung'},
 '36331001':{'name':'Eurosmart CE · Waschtisch · Batteriebetrieb','details':'Sensor · 6-V-Batterie · Waschtisch-Ausführung'},
 '36332000':{'name':'Eurosmart CE · Waschtisch-Wandarmatur','details':'Wandmontage · mit Mischeinrichtung und Thermostat · 6-V-Batterie'},
}

def is_grohe_eurosmart_ce(manufacturer, product):
 return 'grohe' in clean(manufacturer).lower() and 'EUROSMART CE' in clean(product).upper()

def grohe_variant_label(article):
 v=GROHE_VARIANTS[article]
 return f"{article} — {v['name']} — {v['details']}"

CATS=['Produktdatenblatt','Planung & Montage','Montage – Sonderanwendung','Leistungserklärung (DoP)','CE / Konformität','ATEX','Hygiene','Zulassung / Prüfzeugnis','EPD / DGNB / Umwelt','Broschüre / Planung','Sonstiges']

def db():
 c=sqlite3.connect(DB)
 c.execute('CREATE TABLE IF NOT EXISTS components(id INTEGER PRIMARY KEY, project TEXT, manufacturer TEXT, product TEXT, article_no TEXT, confidence INTEGER, status TEXT, docs_searched INTEGER DEFAULT 0)')
 c.execute('CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, component_id INTEGER, doc_type TEXT, title TEXT, source_url TEXT, verified INTEGER DEFAULT 0, confidence INTEGER DEFAULT 0, source_page TEXT DEFAULT "", local_path TEXT DEFAULT "", download_status TEXT DEFAULT "", priority TEXT DEFAULT "")')
 c.execute('CREATE TABLE IF NOT EXISTS component_selections(component_id INTEGER, selection TEXT, PRIMARY KEY(component_id,selection))')
 c.execute('CREATE TABLE IF NOT EXISTS component_application_groups(component_id INTEGER, group_code TEXT, PRIMARY KEY(component_id,group_code))')
 c.execute('CREATE TABLE IF NOT EXISTS projects(name TEXT PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
 c.execute('INSERT OR IGNORE INTO projects(name) SELECT DISTINCT project FROM components WHERE project IS NOT NULL AND TRIM(project) != ""')
 ccols={r[1] for r in c.execute('PRAGMA table_info(components)').fetchall()}
 if 'docs_searched' not in ccols: c.execute('ALTER TABLE components ADD COLUMN docs_searched INTEGER DEFAULT 0')
 if 'manufacturer_product_name' not in ccols: c.execute('ALTER TABLE components ADD COLUMN manufacturer_product_name TEXT DEFAULT ""')
 if 'product_name_confirmed' not in ccols: c.execute('ALTER TABLE components ADD COLUMN product_name_confirmed INTEGER DEFAULT 0')
 cols={r[1] for r in c.execute('PRAGMA table_info(documents)').fetchall()}
 for name,sql in [('confidence','INTEGER DEFAULT 0'),('source_page','TEXT DEFAULT ""'),('local_path','TEXT DEFAULT ""'),('download_status','TEXT DEFAULT ""'),('priority','TEXT DEFAULT ""'),('project_confirmed','INTEGER DEFAULT 0'),('project_decision','TEXT DEFAULT ""'),('project_decision_note','TEXT DEFAULT ""')]:
  if name not in cols: c.execute(f'ALTER TABLE documents ADD COLUMN {name} {sql}')
 c.execute("UPDATE documents SET project_confirmed=0 WHERE title LIKE '%Mapress Therm%Installation / Verarbeitung%' AND project_confirmed=1 AND (project_decision IS NULL OR project_decision='')")
 c.execute("UPDATE documents SET project_confirmed=0,project_decision='',project_decision_note='' WHERE title='Anwendbarkeitsnachweise' AND project_decision='manual_confirmed'")
 c.commit(); return c

def persist_search_docs(con, component_id, docs):
 # Suchergebnisse projektweit speichern. Bereits getroffene Projektbestätigungen bleiben bei erneuter Suche erhalten.
 confirmed_before={(r[0],r[1]):(r[2],r[3],r[4]) for r in con.execute('SELECT title,source_url,project_confirmed,project_decision,project_decision_note FROM documents WHERE component_id=?',(component_id,)).fetchall()}
 con.execute('UPDATE components SET docs_searched=1 WHERE id=?',(component_id,))
 con.execute("DELETE FROM documents WHERE component_id=? AND (local_path IS NULL OR local_path='')",(component_id,))
 for d in docs:
  if not d.get('Relevant'): continue
  online=not d.get('Downloadbar',True)
  verified=1 if online else 0
  dstatus='Online-Nachweis' if online else 'Fundstelle gefunden'
  title=d.get('Titel','Dokument'); url=d.get('URL',''); confirmed,decision,note=confirmed_before.get((title,url),(0,'',''))
  con.execute('INSERT INTO documents(component_id,doc_type,title,source_url,verified,confidence,source_page,local_path,download_status,priority,project_confirmed,project_decision,project_decision_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(component_id,d.get('Kategorie','Sonstiges'),title,url,verified,d.get('Treffer %',0),d.get('Quellseite',''),'',dstatus,d.get('Priorität',''),confirmed,decision,note))
 con.commit()

def get_component_selections(con, component_id):
 return [r[0] for r in con.execute('SELECT selection FROM component_selections WHERE component_id=? ORDER BY selection',(component_id,)).fetchall()]

def save_component_selections(con, component_id, selections):
 con.execute('DELETE FROM component_selections WHERE component_id=?',(component_id,))
 for sel in selections:
  con.execute('INSERT OR IGNORE INTO component_selections(component_id,selection) VALUES(?,?)',(component_id,sel))
 con.commit()

def get_application_groups(con, component_id):
 return [r[0] for r in con.execute('SELECT group_code FROM component_application_groups WHERE component_id=? ORDER BY group_code',(component_id,)).fetchall()]

def save_application_groups(con, component_id, group_codes):
 con.execute('DELETE FROM component_application_groups WHERE component_id=?',(component_id,))
 for code in group_codes:
  con.execute('INSERT OR IGNORE INTO component_application_groups(component_id,group_code) VALUES(?,?)',(component_id,code))
 con.commit()

def ensure_conlit_proofs(con, project, component_id, manufacturer, product, selected_labels):
 """Ordnet die offiziellen ROCKWOOL-Nachweise zu und speichert sie offline.
 Gibt (erfolgreiche_labels, fehler) zurück.
 """
 headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}
 ok=[]; errors=[]
 for label in selected_labels:
  cfg=CONLIT_DOCUMENT_GROUPS[label]; url=cfg['url']; proof=cfg['proof']
  title=f'ROCKWOOL Conlit 150 U – {proof}'
  existing=con.execute('SELECT id,local_path FROM documents WHERE component_id=? AND title=?',(component_id,title)).fetchone()
  if existing and existing[1] and os.path.exists(existing[1]):
   ok.append(label); continue
  try:
   r=requests.get(url,headers=headers,timeout=60,allow_redirects=True); r.raise_for_status()
   if not allowed_download(r.url,'rockwool') or not is_pdf_response(r):
    raise ValueError('Herstellerquelle liefert aktuell keine PDF.')
   folder=os.path.join(DOWNLOAD_ROOT,safe(project),safe(manufacturer),safe(CONLIT_OFFICIAL_NAME)); os.makedirs(folder,exist_ok=True)
   filename=safe(proof)+'.pdf'; path=os.path.join(folder,filename)
   with open(path,'wb') as fh: fh.write(r.content)
   con.execute('DELETE FROM documents WHERE component_id=? AND title=?',(component_id,title))
   con.execute('INSERT INTO documents(component_id,doc_type,title,source_url,verified,confidence,source_page,local_path,download_status,priority,project_confirmed,project_decision,project_decision_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
    (component_id,'Zulassung / Prüfzeugnis',title,url,1,100,'ROCKWOOL · offizieller Anwendbarkeitsnachweis',path,f'Offline · {len(r.content)/1024/1024:.1f} MB','Empfohlen',0,cfg['code'],f'Dokumentgruppe: {label}'))
   ok.append(label)
  except Exception as e:
   errors.append(f'{proof}: {e}')
 con.commit(); return ok,errors

def mapress_selection_docs(selections):
 docs=[]; pages=[]
 install='https://www.geberit.de/sanitaer-rohrleitungssysteme/versorgungssysteme/geberit-mapress/geberit-mapress-therm/'
 for sel in selections:
  if sel=='Systemrohr CrTi':
   cfg=MAPRESS_THERM_GROUPS['Systemrohr CrTi']; pages.append(cfg['page'])
   docs.append({'Kategorie':'Produktdatenblatt','Priorität':'Empfohlen','Titel':'Geberit Mapress Therm Systemrohr CrTi – Produktdatenblatt','Resolver':'Geberit Produktkatalog · verifizierter Online-Nachweis','URL':cfg['page'],'Quellseite':cfg['page'],'Treffer %':100,'Relevant':True,'Downloadbar':False,'Nachweis URL':cfg['page']})
  elif sel in MAPRESS_THERM_FITTINGS:
   cfg=MAPRESS_THERM_FITTINGS[sel]; pages.append(cfg['page'])
   for base in cfg.get('docs',[]):
    d=dict(base); d.update({'URL':cfg['page'],'Quellseite':cfg['page'],'Treffer %':100,'Relevant':True,'Downloadbar':False,'Nachweis URL':cfg['page']}); docs.append(d)
 if selections:
  docs.append({'Kategorie':'Planung & Montage','Priorität':'Anwendungsfall prüfen','Titel':'Geberit Mapress Therm – Installation / Verarbeitung','Resolver':'Geberit Systeminformation · d108 abweichend','URL':install,'Quellseite':install,'Treffer %':100,'Relevant':True,'Downloadbar':False,'Nachweis URL':install})
 # identische Dokumente aus mehreren Teilkomponenten nur einmal führen
 unique=[]; seen=set()
 for d in docs:
  key=(d.get('Kategorie'),d.get('Titel'),d.get('URL'))
  if key not in seen: seen.add(key); unique.append(d)
 return (pages[0] if pages else install),unique

def documentation_light(searched, docs):
 if not searched:
  return '🔴 Noch nicht bearbeitet'
 if not docs:
  return '🟡 Suche ausgeführt · kein Nachweis'
 # docs: priority, verified, local_path, download_status, project_confirmed
 checks=sum(1 for prio,_,_,_,confirmed in docs if prio in ['Anwendungsfall prüfen','Optional / Ausführung prüfen'] and not confirmed)
 recommended=sum(1 for prio,_,_,_,_ in docs if prio=='Empfohlen')
 if checks or recommended==0:
  return '🟡 Prüfung/offene Unterlagen'
 return '🟢 Dokumentation geklärt'

def clean(v):
 if pd.isna(v): return ''
 return re.sub(r'\s+',' ',str(v)).strip()

def detect_header(raw):
 wanted={'hersteller','bezeichnung','artikelnummer'}
 for i,row in raw.iterrows():
  if len(wanted & {clean(x).lower() for x in row.tolist()})>=2:return i
 raise ValueError('Keine passende Kopfzeile gefunden.')

def read_excel(data):
 raw=pd.read_excel(io.BytesIO(data),header=None); h=detect_header(raw); df=pd.read_excel(io.BytesIO(data),header=h).dropna(axis=1,how='all').dropna(axis=0,how='all'); cols={clean(c).lower():c for c in df.columns}; out=pd.DataFrame()
 out['Hersteller']=df[cols.get('hersteller')].map(clean) if cols.get('hersteller') else ''
 out['Bezeichnung']=df[cols.get('bezeichnung')].map(clean) if cols.get('bezeichnung') else ''
 out['Artikelnummer']=df[cols.get('artikelnummer')].map(clean) if cols.get('artikelnummer') else ''
 return out[(out.Hersteller!='')|(out.Bezeichnung!='')].reset_index(drop=True)

def score(r): return min(45+(20 if r['Hersteller'] else 0)+(20 if r['Bezeichnung'] else 0)+(15 if r['Artikelnummer'] else 0),100)
def status(s): return 'Automatisch prüfbar' if s>=95 else ('Bestätigung empfohlen' if s>=75 else 'Manuelle Prüfung')
def safe(v): return (re.sub(r'[^A-Za-z0-9ÄÖÜäöüß._-]+','_',clean(v)).strip('._')[:120] or 'dokument')

def product_key(m,p):
 ml=clean(m).lower(); pu=clean(p).upper()
 # Herstellerbezeichnungen aus Excel dürfen Zusätze enthalten.
 if 'rockwool' in ml: ml='rockwool'
 elif 'trox' in ml: ml='trox'
 # Unterstützte ROCKWOOL-Produktfamilien robust normalisieren.
 if ml=='rockwool':
  if 'CONLIT' in pu and ('150 U' in pu or pu.endswith(' U') or pu=='CONLIT U'): return (ml,'CONLIT U')
  if re.search(r'(^|\D)800($|\D)', pu): return (ml,'800')
 return (ml,pu)

def is_rockwool_conlit(manufacturer, product):
 return 'rockwool' in clean(manufacturer).lower() and product_key(manufacturer,product)[1]=='CONLIT U'

def is_trox_fk2(manufacturer, product):
 return clean(manufacturer).lower()=='trox' and clean(product).upper()=='FK2-EU'

FK2_APPLICATION_GROUPS={
 'fk2_standard':'Standardanwendung',
 'fk2_atex':'ATEX / explosionsgefährdeter Bereich',
 'fk2_special_mounting':'Montage-Sonderanwendung',
}

def fk2_check_group(doc_type):
 if doc_type=='ATEX': return 'fk2_atex'
 if doc_type=='Montage – Sonderanwendung': return 'fk2_special_mounting'
 return ''

def _fk2_version_key(title):
 # Neueste Fassung aus TROX-Dateinamen bevorzugen (z. B. V3_2025_08 bzw. 2022_07_06).
 t=clean(title)
 dates=re.findall(r'(20\d{2})[_-](\d{2})(?:[_-](\d{2}))?',t)
 date=max(((int(y),int(m),int(d or 0)) for y,m,d in dates),default=(0,0,0))
 vm=re.search(r'(?:^|[_-])V(\d+)(?:[_-]|\.)',t,re.I)
 version=int(vm.group(1)) if vm else 0
 return date+(version,)

def fk2_required_group_rows(rows, group_code):
 relevant=[r for r in rows if fk2_check_group(r[1])==group_code]
 if group_code!='fk2_atex': return relevant
 # ATEX besteht aus Rollen, nicht aus allen historischen Dateien:
 # 1) aktuelle ATEX-Betriebs-/Zusatzanleitung, 2) aktuelle CE/ATEX-Konformitätsunterlage.
 manuals=[r for r in relevant if 'A000' in clean(r[2]).upper() or re.search(r'(?:^|[_-])V\d+',clean(r[2]),re.I)]
 conformity=[r for r in relevant if 'CE' in clean(r[2]).upper() and 'ATEX' in clean(r[2]).upper()]
 required=[]
 if manuals: required.append(max(manuals,key=lambda r:_fk2_version_key(r[2])))
 if conformity: required.append(max(conformity,key=lambda r:_fk2_version_key(r[2])))
 # Fallback für unerwartete TROX-Namensänderungen: mindestens den neuesten ATEX-Treffer verlangen.
 if not required and relevant: required=[max(relevant,key=lambda r:_fk2_version_key(r[2]))]
 seen=set(); out=[]
 for r in required:
  if r[0] not in seen: out.append(r); seen.add(r[0])
 return out

def fk2_group_complete(rows, group_code):
 required=fk2_required_group_rows(rows,group_code)
 if not required: return False
 return all(bool((r[5] and os.path.exists(r[5])) or r[6]=='Online-Nachweis') for r in required)

def save_fk2_application(con, component_id, selected_codes, saved_rows):
 # Standard ist immer die Basis; gespeichert werden nur die zusätzlich benötigten Dokumentgruppen.
 save_application_groups(con,component_id,['fk2_standard']+list(selected_codes))
 required_ids={g:{r[0] for r in fk2_required_group_rows(saved_rows,g)} for g in selected_codes}
 for r in saved_rows:
  docid,dtype,title,url,dconf,path,dstatus,prio,confirmed,source_page,decision,note=r
  group=fk2_check_group(dtype)
  if not group: continue
  if group not in selected_codes:
   con.execute('UPDATE documents SET project_confirmed=1,project_decision=?,project_decision_note=? WHERE id=?',
    ('fk2_not_required','Für dieses Projekt nicht ausgewählt; Standardanwendung bzw. andere Dokumentgruppe maßgeblich.',docid))
  elif docid not in required_ids.get(group,set()):
   con.execute('UPDATE documents SET project_confirmed=1,project_decision=?,project_decision_note=? WHERE id=?',
    ('fk2_superseded','Ältere bzw. zusätzliche Fassung; für die Vollständigkeit wird die aktuelle erforderliche Dokumentrolle bewertet.',docid))
  else:
   available=bool((path and os.path.exists(path)) or dstatus=='Online-Nachweis')
   con.execute('UPDATE documents SET project_confirmed=?,project_decision=?,project_decision_note=? WHERE id=?',
    (1 if available else 0,'fk2_group_complete' if available else 'fk2_group_required',
     f'Dokumentgruppe {FK2_APPLICATION_GROUPS[group]} ist projektbezogen ausgewählt.' + (' Aktueller Nachweis ist vorhanden.' if available else ' Aktueller Nachweis muss noch offline gespeichert oder verifiziert werden.'),docid))
 con.commit()


CONLIT_OFFICIAL_NAME='ROCKWOOL Conlit® 150 U'
# Nur dokumentationsrelevante Gruppen: Varianten werden zusammengefasst, wenn dieselben Nachweise gelten.
CONLIT_DOCUMENT_GROUPS={
 'Nichtbrennbare Versorgungs-/Rohrleitungen (einschl. metallische Gasleitungen)':{
  'code':'conlit_noncombustible','proof':'abP P-3725/4130-MPA BS','url':'https://www.rockwool.com/siteassets/rw-d/prufzeugnisse/rohrleitungen/pz-abp-conlit-150u-nichtbrennbare-rohrleitungen-r90-rockwool.pdf',
  'note':'Dokumentgruppe für nichtbrennbare Rohrleitungen; metallische Gasleitungen werden nicht separat angeboten, weil sie derselben Nachweisgruppe zugeordnet werden.'},
 'Brennbare Versorgungsleitungen':{
  'code':'conlit_combustible_supply','proof':'abP P-3726/4140-MPA BS','url':'https://www.rockwool.com/siteassets/rw-d/prufzeugnisse/rohrleitungen/pz-abp-conlit-150u-brennbare-rohrleitungen-r90-rockwool.pdf',
  'note':'Eigene Dokumentgruppe für brennbare Versorgungsleitungen.'},
 'Mischinstallationen bei Versorgungsleitungen':{
  'code':'conlit_mixed','proof':'aBG Z-19.53-2426','url':'https://www.rockwool.com/syssiteassets/rw-d/prufzeugnisse/rohrleitungen/pz-abg-rohrabschottung-r90-fuer-mischinstallationen-bei-versorgungsleitungen-rockwool.pdf',
  'note':'Eigene Dokumentgruppe für Mischinstallationen bei Versorgungsleitungen.'},
 'Brennbare Gasrohrleitungen (Kunststoff / Mehrschichtverbund)':{
  'code':'conlit_combustible_gas','proof':'aBG Z-19.53-2436','url':'https://www.rockwool.com/syssiteassets/rw-d/prufzeugnisse/rohrleitungen/pz-rohrab-kunststoff-gasrohrleitungen-conlit-150u-schale-rockwool.pdf',
  'note':'Eigene Dokumentgruppe für brennbare Gasrohrleitungen; zusätzliche Randbedingungen des Nachweises sind zu beachten.'},
}

def classify(title,url,manufacturer):
 b=(title+' '+url).lower()
 if 'atex' in b:return 'ATEX'
 if any(x in b for x in ['_dop_','leistungserklärung','declaration-of-performance','declaration of performance']):return 'Leistungserklärung (DoP)'
 if any(x in b for x in ['hygiene','hygien','_hc_']):return 'Hygiene'
 if any(x in b for x in ['epd','environmental product','dgnb','blauer-engel','eurofins','indoor-air']):return 'EPD / DGNB / Umwelt'
 if any(x in b for x in ['datenblatt','produktdatenblatt','datasheet','data-sheet','_pd_','db-']):return 'Produktdatenblatt'
 # Eindeutige CE-Dateinamen vor generischen Zertifikatsbegriffen prüfen.
 if any(x in b for x in ['konform','conform','_ce_','ce-']) and 'atex' not in b:return 'CE / Konformität'
 if any(x in b for x in ['abp','abg','zulassung','bauartgenehmigung','anwendbarkeitsnachweis','prüfzeugnis','prufzeugnis','dibt','zertifikat','certificate']):return 'Zulassung / Prüfzeugnis'
 if any(x in b for x in ['montage','installation','betriebsanleitung','operating','_iom_']):
  if manufacturer=='trox' and any(x in b for x in ['_gl_','_glk_','_wa_','_we_','_oda_','rm-o','_sv_','_e3_','_ew_']):return 'Montage – Sonderanwendung'
  return 'Planung & Montage'
 if re.search(r'(^|[/_-])lc([_.-]|$)', b):return 'Sonstiges'
 if any(x in b for x in ['broschüre','broschuere','brochure','planungs','ratgeber','handbuch']):return 'Broschüre / Planung'
 return 'Sonstiges'

def priority(cat,title,url,manufacturer,product):
 b=(title+' '+url).lower()
 if cat in ['Produktdatenblatt','Leistungserklärung (DoP)','CE / Konformität','Hygiene','EPD / DGNB / Umwelt']: return 'Empfohlen'
 if cat=='Planung & Montage': return 'Empfohlen'
 if cat in ['ATEX','Montage – Sonderanwendung']: return 'Optional / Ausführung prüfen'
 if cat=='Zulassung / Prüfzeugnis': return 'Anwendungsfall prüfen' if manufacturer=='rockwool' else 'Empfohlen'
 if cat=='Broschüre / Planung': return 'Optional'
 return 'Optional'

def relevance(product,title,url):
 b=(title+' '+url).lower(); p=product.lower()
 aliases=[p]
 if p=='conlit u': aliases+=['conlit 150 u','conlit-150-u','conlit-150u']
 if p=='800': aliases+=['rockwool 800','rockwool-800']
 return any(a in b for a in aliases)

def resolve_product_page(manufacturer, product):
 key=product_key(manufacturer,product)
 if key not in PRODUCTS:
  raise ValueError('Für dieses Produkt ist die automatische Herstellersuche in v0.4.4 noch nicht freigeschaltet.')
 ml=manufacturer.lower(); allowed='trox.de' if ml=='trox' else 'rockwool.com'
 errors=[]
 for candidate in PRODUCTS[key]:
  try:
   host=urlparse(candidate).netloc.lower()
   if allowed not in host:
    continue
   r=requests.get(candidate,headers={'User-Agent':'Mozilla/5.0 (TGA Product Finder v0.4.4)'},timeout=25,allow_redirects=True)
   final_host=urlparse(r.url).netloc.lower()
   if allowed not in final_host:
    errors.append(f'{candidate}: Weiterleitung außerhalb der Herstellerdomain')
    continue
   if r.status_code==200:
    return r.url, r
   errors.append(f'{candidate}: HTTP {r.status_code}')
  except requests.RequestException as e:
   errors.append(f'{candidate}: {e}')
 raise ValueError('Keine gültige offizielle Produktseite erreichbar. Geprüft: ' + ' | '.join(errors))

def rockwool_context(a):
 # Kontext bewusst klein halten: höchstens der direkte Link-Container.
 # Große Elterncontainer enthalten bei ROCKWOOL oft mehrere Dokumentbereiche
 # und sogar Footer/Navigation und würden Kategorien falsch "vererben".
 parts=[]
 for node in [a, a.parent]:
  if node is not None and hasattr(node,'get_text'):
   t=clean(node.get_text(' ',strip=True))
   if t and len(t) <= 600 and t not in parts: parts.append(t)
 return ' '.join(parts)[:800]

def rockwool_noise(title,url):
 b=(title+' '+url).lower()
 terms=['allgemeine einkaufsbedingungen','aeb','allgemeine geschäftsbedingungen','agb',
        'cookie-erklärung','cookie erklaerung','datenschutz','impressum','kontakt',
        'nutzungsbedingungen','nutzungsrechte marke','zum haupt-inhalt springen',
        'zurück zu produkte','zurueck zu produkte','rockcommerce','webshop',
        'tools und rechner','jetzt ausprobieren']
 return any(x in b for x in terms)

def find_docs(manufacturer,product):
 page,r=resolve_product_page(manufacturer,product); key=product_key(manufacturer,product); ml=key[0]; allowed='trox.de' if ml=='trox' else 'rockwool.com'
 soup=BeautifulSoup(r.text,'html.parser'); found=[]; seen=set()
 for a in soup.find_all('a',href=True):
  href=urljoin(page,a['href']); title=clean(a.get_text(' ',strip=True)); host=urlparse(href).netloc.lower()
  if allowed not in host: continue
  if ml=='rockwool' and rockwool_noise(title,href): continue
  context=rockwool_context(a) if ml=='rockwool' else ''
  blob=(title+' '+href+' '+context).lower()
  if not ('.pdf' in blob or 'download' in blob or 'herunterladen' in blob or any(x in blob for x in ['datenblatt','montage','anwendbarkeits','zertifikat','certificate','epd','dop','leistungserklärung','konform','pdf','blauer engel','eurofins'])): continue
  sig=href.split('#')[0].rstrip('/')
  if sig in seen:continue
  seen.add(sig)
  classify_title=(title+' '+context) if ml=='rockwool' else title
  cat=classify(classify_title,href,ml)
  if ml=='rockwool':
   meaningful=cat in ['Produktdatenblatt','Leistungserklärung (DoP)','Planung & Montage','Zulassung / Prüfzeugnis','EPD / DGNB / Umwelt','CE / Konformität','Hygiene']
   # Deutsche Conlit 150 U: ROCKWOOL nennt P-NDS04-417 als Verwendbarkeitsnachweis,
   # nicht den generischen DoP-Download als produktspezifische Leistungserklärung.
   if product_key(manufacturer,product)[1]=='CONLIT U' and cat=='Leistungserklärung (DoP)': meaningful=False
   # Generische Download-Links gelten nur dann als relevant, wenn ihr enger
   # Container tatsächlich eine konkrete Dokumentkategorie erkennen lässt.
   generic=title.lower() in ['herunterladen pdf','download pdf','pdf herunterladen','downloads','herunterladen']
   rel=meaningful and (not generic or cat!='Sonstiges')
  else:
   rel=relevance(product,title,href) and cat!='Sonstiges'
  conf=55+(25 if rel else 0)+(15 if cat!='Sonstiges' else 0)+(5 if allowed in host else 0)
  display_title=title or os.path.basename(urlparse(href).path)
  if ml=='rockwool' and title.lower() in ['herunterladen pdf','download pdf','pdf herunterladen'] and cat!='Sonstiges':
   display_title=f'{cat} – {title}'
  resolver='Direkt / Herstellerseite'; downloadbar=True; nachweis_url=''
  if ml=='rockwool' and 'eurofins' in display_title.lower() and product_key(manufacturer,product)[1] in ['800','CONLIT U']: resolver='Zertifikatsregister → Produkt-PDF'
  if ml=='rockwool' and 'blauer engel' in display_title.lower():
   resolver='Offizielles Umweltzeichen-Register'; downloadbar=False
   nachweis_url=ROCKWOOL_DIRECT_CERTIFICATES.get(product_key(manufacturer,product)[1],ROCKWOOL_DIRECT_CERTIFICATES.get('800',{})).get('blue_angel_registry','')
  if ml=='rockwool' and cat=='Leistungserklärung (DoP)': resolver='DoP-Kennung '+ROCKWOOL_DOP_IDS.get(product_key(manufacturer,product)[1],'')
  found.append({'Kategorie':cat,'Priorität':priority(cat,classify_title,href,ml,product),'Titel':display_title,'Treffer %':min(conf,100),'URL':href,'Quellseite':page,'Relevant':rel,'Resolver':resolver,'Downloadbar':downloadbar,'Nachweis URL':nachweis_url})
 found.sort(key=lambda d:(not d['Relevant'], {'Empfohlen':0,'Anwendungsfall prüfen':1,'Optional / Ausführung prüfen':2,'Optional':3}.get(d['Priorität'],4),-d['Treffer %'],d['Kategorie'],d['Titel']))
 return page,found

def grohe_product_page(article):
 return f'https://www.grohe.de/de_de/-{clean(article)}.html'

def find_grohe_docs(article):
 article=clean(article)
 if article not in GROHE_VARIANTS: raise ValueError('GROHE-Variante ist nicht bestätigt.')
 page=grohe_product_page(article)
 # v0.5.3: Verifizierte, artikelnummernbezogene GROHE-Unterlagen zuerst verwenden.
 # Keine Navigation der Produktseite wird mehr als Dokument interpretiert.
 docs=[]
 for d in GROHE_VERIFIED_DOCS.get(article,[]):
  row=dict(d)
  row.update({'Treffer %':100,'Quellseite':page,'Relevant':True})
  row.setdefault('Downloadbar',True)
  row.setdefault('Nachweis URL','')
  docs.append(row)
 return page,docs

def allowed_download(url,manufacturer):
 host=urlparse(url).netloc.lower(); ml=manufacturer.lower()
 if ml=='trox': return 'trox.de' in host
 if ml=='grohe': return ('grohe.de' in host) or ('grohe.com' in host) or ('grohe.co.za' in host)
 return ('rockwool.com' in host) or ('brandcommunity.rockwool.com' in host)

def is_pdf_response(r):
 data=r.content; ctype=(r.headers.get('content-type') or '').lower()
 return 'application/pdf' in ctype or data[:5]==b'%PDF-' or '.pdf' in r.url.lower()

def fetch_best_pdf_from_page(page_url, manufacturer, phrases, doc=None, max_candidates=30):
 """Findet auf einer offiziellen Herstellerseite den bestpassenden echten PDF-Link."""
 headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
 r=requests.get(page_url,headers=headers,timeout=60,allow_redirects=True); r.raise_for_status()
 if not allowed_download(r.url,manufacturer): raise ValueError('Spezialquelle verlässt die Herstellerdomain.')
 soup=BeautifulSoup(r.text,'html.parser'); candidates=[]; seen=set()
 wanted=[x.lower() for x in phrases if x]
 for a in soup.find_all('a',href=True):
  href=urljoin(r.url,a['href']); host=urlparse(href).netloc.lower(); title=clean(a.get_text(' ',strip=True)); blob=(title+' '+href).lower()
  if 'rockwool.com' not in host or href in seen: continue
  seen.add(href)
  if rockwool_noise(title,href): continue
  score=sum(35 for x in wanted if x in blob)
  if '.pdf' in blob: score+=60
  if any(x in blob for x in ['download','herunterladen']): score+=10
  if score: candidates.append((score,href,title))
 candidates.sort(reverse=True)
 for _,href,_ in candidates[:max_candidates]:
  try:
   rr=requests.get(href,headers=headers,timeout=60,allow_redirects=True); rr.raise_for_status()
   if allowed_download(rr.url,manufacturer) and is_pdf_response(rr): return rr
  except requests.RequestException:
   pass
 raise ValueError(f'Keine echte PDF in der ROCKWOOL-Spezialquelle gefunden ({len(candidates)} Kandidat(en)).')

def fetch_pdf_near_exact_title(page_url, manufacturer, exact_title):
 """ROCKWOOL-Dokumentkarten inkl. Asset-/JSON-Metadaten robust auflösen."""
 headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
 r=requests.get(page_url,headers=headers,timeout=60,allow_redirects=True); r.raise_for_status()
 if not allowed_download(r.url,manufacturer): raise ValueError('Zertifikatsquelle verlässt die Herstellerdomain.')
 soup=BeautifulSoup(r.text,'html.parser'); target=exact_title.lower(); candidates=[]; seen=set()
 def add(raw,score=50):
  if not raw: return
  raw=str(raw).strip().replace('\\u002F','/').replace('\\/','/').replace('&amp;','&')
  if raw.startswith('//'): raw='https:'+raw
  href=urljoin(r.url,raw)
  host=urlparse(href).netloc.lower(); blob=href.lower()
  if href in seen: return
  if not (('rockwool.com' in host) or ('brandcommunity.rockwool.com' in host)): return
  if any(x in blob for x in ['javascript:','mailto:']): return
  seen.add(href)
  if '.pdf' in blob: score+=150
  if any(x in blob for x in ['asset','download','media']): score+=35
  candidates.append((score,href))
 # 1) Exakte Dokumentkarte + alle Attribute der Karte/Eltern (ROCKWOOL legt URLs teils in data-* ab).
 for node in soup.find_all(string=lambda x: x and target in clean(x).lower()):
  parent=node.parent
  for depth in range(9):
   if parent is None: break
   context=clean(parent.get_text(' ',strip=True)).lower()
   if target in context:
    for tag in parent.find_all(True):
     txt=clean(tag.get_text(' ',strip=True)).lower()
     base=120 if (target in txt or 'download' in txt or 'herunterladen' in txt) else 70
     for attr,val in tag.attrs.items():
      vals=val if isinstance(val,list) else [val]
      for raw in vals:
       if isinstance(raw,str) and (raw.startswith(('http','/','//')) or '.pdf' in raw.lower() or 'asset' in raw.lower() or 'download' in raw.lower()):
        add(raw,base + (25 if str(attr).startswith('data-') else 0))
   if len(context)>12000: break
   parent=parent.parent
 # 2) Roh-HTML/JSON rund um den exakten Titel. Erfasst escaped URLs und CMS-Asset-Metadaten.
 raw=r.text; pos=raw.lower().find(target)
 if pos>=0:
  window=raw[max(0,pos-30000):pos+50000]
  patterns=[
   r'https?:\\?/\\?/[^"\'<> ]+',
   r'(?:(?:href|url|downloadUrl|downloadURL|assetUrl|assetURL|fileUrl|fileURL|src)["\']?\\s*[:=]\\s*["\'])([^"\']+)',
   r'([/][^"\'<> ]+(?:\\.pdf|/asset(?:\\?|/)|/download(?:\\?|/))[^"\'<> ]*)'
  ]
  for pat in patterns:
   for m in re.finditer(pat,window,re.I):
    val=m.group(1) if m.lastindex else m.group(0)
    add(val,95)
 # 3) Kandidaten testen; HTML-Zwischenseiten einmal nach einer echten PDF/Asset-URL auflösen.
 candidates.sort(reverse=True)
 checked=0
 for _,href in candidates[:60]:
  try:
   rr=requests.get(href,headers=headers,timeout=60,allow_redirects=True); rr.raise_for_status(); checked+=1
   if allowed_download(rr.url,manufacturer) and is_pdf_response(rr): return rr
   ctype=(rr.headers.get('content-type') or '').lower()
   if 'html' in ctype and len(rr.content)<8_000_000:
    sub=BeautifulSoup(rr.text,'html.parser')
    for tag in sub.find_all(True):
     for attr in ['href','src','data-href','data-url','data-download-url','data-file','data-src']:
      val=tag.get(attr)
      if not val: continue
      u=urljoin(rr.url,val); ul=u.lower()
      if '.pdf' not in ul and 'asset' not in ul and 'download' not in ul: continue
      try:
       r2=requests.get(u,headers=headers,timeout=60,allow_redirects=True); r2.raise_for_status()
       if allowed_download(r2.url,manufacturer) and is_pdf_response(r2): return r2
      except requests.RequestException: pass
  except requests.RequestException: pass
 raise ValueError(f'Zertifikatskarte bestätigt, aber echte PDF technisch nicht auflösbar ({checked} von {len(candidates)} Kandidat(en) geprüft).')

def resolve_rockwool_special(product, doc):
 """Dokumenttypabhängige ROCKWOOL-Resolver für Zertifikate und DoP."""
 p=product_key('rockwool',product)[1]; title=(doc or {}).get('Titel','').lower(); cat=(doc or {}).get('Kategorie','')
 if 'eurofins' in title and p=='CONLIT U':
  cfg=ROCKWOOL_DIRECT_CERTIFICATES['CONLIT U']
  return fetch_pdf_near_exact_title(cfg['eurofins_page'],'rockwool',cfg['eurofins_title'])
 if 'eurofins' in title and p=='800':
  # Verifiziertes ROCKWOOL-Asset: Indoor Air Comfort Gold für ROCKWOOL 800/810.
  headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
  rr=requests.get(ROCKWOOL_DIRECT_CERTIFICATES['800']['eurofins'],headers=headers,timeout=60,allow_redirects=True); rr.raise_for_status()
  if allowed_download(rr.url,'rockwool') and is_pdf_response(rr): return rr
  raise ValueError('Das verifizierte Eurofins-Zertifikat liefert aktuell keine PDF.')
 if 'blauer engel' in title:
  # Der belastbare Nachweis liegt im offiziellen Blauer-Engel-Produktregister.
  # Kein PDF vortäuschen: dieser Treffer wird in der UI als Online-Nachweis geführt.
  return None
 if cat=='Leistungserklärung (DoP)' or 'leistungserklärung' in title or 'dop' in title:
  dop=ROCKWOOL_DOP_IDS.get(p)
  if dop:
   # ROCKWOOLs deutsche DoP-Suche ist dynamisch. Die Kennung wird zuerst gegen offizielle
   # ROCKWOOL-Assets aufgelöst; bekannte Produktkennung bleibt die harte Zuordnungsbedingung.
   known={'DE0721042201':'https://www.rockwool.com/syssiteassets/rw-pl/materialy-do-pobrania/dokumentacja-produktowa/deklaracja-waciwoci-uytkowych/DoP_ROCKWOOL_800_DE0721042201.pdf.pdf'}
   if dop in known:
    headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
    rr=requests.get(known[dop],headers=headers,timeout=60,allow_redirects=True); rr.raise_for_status()
    if allowed_download(rr.url,'rockwool') and is_pdf_response(rr): return rr
 return None

def resolve_pdf_url(url,manufacturer,doc=None,product=''):
 """Direkte PDF verwenden; bei ROCKWOOL-HTML eine Ebene nach der echten PDF durchsuchen."""
 if not allowed_download(url,manufacturer): raise ValueError('Quelle gehört nicht zur freigegebenen Herstellerdomain.')
 headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
 # GROHEs ältere PDF-Generatoren blockieren einfache Script-Requests teilweise mit HTTP 403.
 # Bei GROHE senden wir deshalb normale Browser-Header + Referer und versuchen genau einmal erneut.
 if manufacturer.strip().lower()=='grohe':
  headers.update({'Accept':'application/pdf,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8','Accept-Language':'de-DE,de;q=0.9,en;q=0.7','Referer':'https://www.grohe.de/','Cache-Control':'no-cache'})
 r=requests.get(url,headers=headers,timeout=60,allow_redirects=True)
 if r.status_code==403 and manufacturer.strip().lower()=='grohe':
  retry_headers=dict(headers); retry_headers['Referer']='https://www.grohe.co.za/' if 'grohe.co.za' in url.lower() else 'https://www.grohe.de/'
  r=requests.get(url,headers=retry_headers,timeout=60,allow_redirects=True)
 r.raise_for_status()
 if not allowed_download(r.url,manufacturer): raise ValueError('Weiterleitung verlässt die Herstellerdomain.')
 if is_pdf_response(r): return r
 if manufacturer.strip().lower()=='grohe':
  soup=BeautifulSoup(r.text,'html.parser'); candidates=[]; seen=set()
  for a in soup.find_all('a',href=True):
   href=urljoin(r.url,a['href']); blob=(clean(a.get_text(' ',strip=True))+' '+href).lower()
   if href in seen or not allowed_download(href,'grohe'): continue
   seen.add(href)
   if '.pdf' in blob or 'download' in blob:
    candidates.append(href)
  for href in candidates[:20]:
   try:
    rr=requests.get(href,headers=headers,timeout=60,allow_redirects=True); rr.raise_for_status()
    if allowed_download(rr.url,'grohe') and is_pdf_response(rr): return rr
   except requests.RequestException: pass
  raise ValueError(f'GROHE-Link liefert noch keine echte PDF ({len(candidates)} Download-Kandidat(en) geprüft).')
 if manufacturer.strip().lower()!='rockwool': raise ValueError('Link liefert keine PDF-Datei.')
 special=resolve_rockwool_special(product,doc or {})
 if special is not None: return special

 soup=BeautifulSoup(r.text,'html.parser'); candidates=[]; seen=set()
 wanted_cat=(doc or {}).get('Kategorie',''); wanted_title=(doc or {}).get('Titel','').lower()
 for a in soup.find_all('a',href=True):
  href=urljoin(r.url,a['href']); host=urlparse(href).netloc.lower(); title=clean(a.get_text(' ',strip=True)); blob=(title+' '+href).lower()
  if 'rockwool.com' not in host or href in seen: continue
  seen.add(href)
  # Nur echte/naheliegende Dokumentdownloads verfolgen, keine Navigation.
  if rockwool_noise(title,href): continue
  if not ('.pdf' in blob or 'download' in blob or 'herunterladen' in blob): continue
  cat=classify(title,href,'rockwool')
  score=0
  if '.pdf' in blob: score+=50
  if cat==wanted_cat and cat!='Sonstiges': score+=35
  if any(x in blob for x in ['download','herunterladen']): score+=10
  if wanted_title and any(w in blob for w in wanted_title.split() if len(w)>5): score+=5
  candidates.append((score,href))
 candidates.sort(reverse=True)
 errors=[]
 for _,href in candidates[:12]:
  try:
   rr=requests.get(href,headers=headers,timeout=60,allow_redirects=True); rr.raise_for_status()
   if allowed_download(rr.url,manufacturer) and is_pdf_response(rr): return rr
  except requests.RequestException as e: errors.append(str(e))
 raise ValueError(f'Keine echte PDF auf der ROCKWOOL-Folgeseite gefunden ({len(candidates)} Download-Kandidat(en) geprüft).')

def download(project,m,p,d):
 r=resolve_pdf_url(d['URL'],m,d,p)
 data=r.content
 folder=os.path.join(DOWNLOAD_ROOT,safe(project),safe(m),safe(p)); os.makedirs(folder,exist_ok=True); raw=os.path.basename(urlparse(r.url).path) or safe(d['Titel'])+'.pdf'
 if not raw.lower().endswith('.pdf'):raw+='.pdf'
 path=os.path.join(folder,safe(raw[:-4])+'.pdf')
 if os.path.exists(path): path=os.path.splitext(path)[0]+'_'+hashlib.sha1(r.url.encode()).hexdigest()[:8]+'.pdf'
 with open(path,'wb') as f:f.write(data)
 return path,len(data),r.url

def google_url(m,p,a=''):
 domain=DOMAINS.get(m.lower(),''); q=' '.join(x for x in [m,p,a] if x); q=(f'site:{domain} '+q) if domain else q
 return 'https://www.google.com/search?q='+urllib.parse.quote(q)


APP_VERSION = "1.5.0"
# Dieser Endpunkt wird aktiviert, sobald ein fester Update-Speicher eingerichtet ist.
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/FabienneBoese/TGA-Product-Finder-Updates/main/update_manifest.json"
UPDATE_CHANNEL_FILE = Path.home() / "AppData" / "Local" / "TGA Product Finder" / "update_channel.json"

def _get_update_manifest_url():
    """Read the update channel without touching project data."""
    try:
        if UPDATE_CHANNEL_FILE.exists():
            cfg = json.loads(UPDATE_CHANNEL_FILE.read_text(encoding="utf-8"))
            return str(cfg.get("manifest_url", "")).strip()
    except Exception:
        pass
    return UPDATE_MANIFEST_URL


def _version_tuple(value):
    try:
        return tuple(int(x) for x in str(value).strip().lstrip("v").split("."))
    except Exception:
        return (0,)


def download_update_package(download_url, expected_sha256=""):
    """Download an update package and verify its SHA256 when supplied."""
    r = requests.get(download_url, timeout=60)
    r.raise_for_status()
    data = r.content
    actual_sha256 = hashlib.sha256(data).hexdigest().lower()
    expected = str(expected_sha256 or "").strip().lower()
    if expected and actual_sha256 != expected:
        raise ValueError("Sicherheitsprüfung fehlgeschlagen: SHA256 stimmt nicht überein.")
    update_dir = Path(tempfile.gettempdir()) / "TGA_Product_Finder_Update"
    update_dir.mkdir(parents=True, exist_ok=True)
    target = update_dir / "TGA_Product_Finder_Update.zip"
    target.write_bytes(data)
    return target, actual_sha256

def install_downloaded_update(zip_path):
    """Start the standalone PowerShell updater directly, without a CMD bridge."""
    import subprocess
    package = Path(zip_path).resolve()
    root = Path.home() / "AppData" / "Local" / "TGA Product Finder"
    updater = root / "TGA_Updater.ps1"
    start_log = root / "updater_start.log"

    if not package.exists():
        raise FileNotFoundError(f"Update-Paket fehlt: {package}")
    if not updater.exists():
        raise FileNotFoundError(f"Windows-Updater fehlt: {updater}")

    start_log.write_text(
        "Direktstart vorbereitet.\n"
        f"Updater: {updater}\n"
        f"Package: {package}\n",
        encoding="utf-8"
    )

    cmd = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(updater),
        "-Package", str(package),
    ]
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    process = subprocess.Popen(
        cmd,
        cwd=str(root),
        creationflags=flags,
        close_fds=False,
    )
    start_log.write_text(
        start_log.read_text(encoding="utf-8") +
        f"PowerShell-Prozess gestartet. PID: {process.pid}\n",
        encoding="utf-8"
    )
    return updater

def check_for_update():
    """Read the manifest through GitHub's API to avoid stale raw-CDN data."""
    import base64
    manifest_url = _get_update_manifest_url()
    if not manifest_url:
        return {"configured": False, "current": APP_VERSION}

    headers = {
        "Accept": "application/vnd.github+json",
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "User-Agent": "TGA-Product-Finder-Updater",
    }
    api = "https://api.github.com/repos/FabienneBoese/TGA-Product-Finder-Updates/contents/update_manifest.json"
    info = None
    errors = []
    source = ""

    try:
        r = requests.get(f"{api}?ref=main&t={time.time_ns()}", timeout=10, headers=headers)
        r.raise_for_status()
        payload = r.json()
        encoded = str(payload.get("content", "")).replace("\n", "")
        info = json.loads(base64.b64decode(encoded).decode("utf-8"))
        source = "GitHub API"
    except Exception as exc:
        errors.append(f"GitHub API: {exc}")

    if info is None:
        try:
            sep = "&" if "?" in manifest_url else "?"
            r = requests.get(
                f"{manifest_url}{sep}t={time.time_ns()}",
                timeout=10,
                headers=headers,
            )
            r.raise_for_status()
            info = r.json()
            source = "Raw-Fallback"
        except Exception as exc:
            errors.append(f"Raw: {exc}")
            return {"configured": True, "current": APP_VERSION, "error": " | ".join(errors)}

    latest = str(info.get("version", "")).strip()
    url = str(info.get("download_url", "")).strip()
    sha256 = str(info.get("sha256", "")).strip().lower()
    return {
        "configured": True,
        "current": APP_VERSION,
        "latest": latest,
        "server_version": latest,
        "download_url": url,
        "sha256": sha256,
        "source": source,
        "available": bool(latest and url and _version_tuple(latest) > _version_tuple(APP_VERSION)),
    }


st.set_page_config(page_title='TGA Product Finder 1.0.3',page_icon='🏗️',layout='wide')
st.title(f'🏗️ TGA Product Finder · Version {APP_VERSION}')
st.caption('Intelligente Dokumentenmappe · projektbezogene Offline-Dokumente')

with st.sidebar:
    st.header("Programm")
    st.write(f"Installierte Version: **v{APP_VERSION}**")
    if st.button("Nach Updates suchen", key="check_app_update"):
        st.session_state["update_check"] = check_for_update()
    _u = st.session_state.get("update_check")
    if _u:
        if not _u.get("configured"):
            st.info("Die Update-Funktion ist aktiv. Der feste Online-Updatekanal ist noch nicht verbunden.")
        elif _u.get("error"):
            st.warning("Update-Prüfung derzeit nicht möglich.")
        elif _u.get("available"):
            st.success(f"Neue Version verfügbar: v{_u.get('latest')}")
            if st.button("Update herunterladen", key="download_app_update"):
                try:
                    _path, _hash = download_update_package(_u.get("download_url"), _u.get("sha256"))
                    st.session_state["downloaded_update_path"] = str(_path)
                    st.success("Update wurde heruntergeladen und geprüft.")
                    st.info("Das Update ist bereit zur Installation.")
                    if False and st.button("Update jetzt installieren", key="install_downloaded_app_update_legacy"):
                        try:
                            install_downloaded_update(_path)
                            st.success("Installer gestartet. Das Update-Fenster übernimmt jetzt die Installation.")
                            st.info("Deine Projektdaten im Data-Ordner bleiben unangetastet.")
                        except Exception as exc:
                            st.error(f"Update konnte nicht installiert werden: {exc}")
                except Exception as exc:
                    st.error(f"Update konnte nicht heruntergeladen werden: {exc}")
        else:
            st.success("Du verwendest die aktuelle Version.")

# v1.4.0: Projektverwaltung – alte Projekte werden aus Komponenten übernommen.
st.subheader('🏗️ Projektverwaltung')
with db() as project_db:
 existing_projects=[r[0] for r in project_db.execute('SELECT name FROM projects ORDER BY name COLLATE NOCASE').fetchall()]
if not existing_projects:
 with db() as project_db:
  project_db.execute('INSERT OR IGNORE INTO projects(name) VALUES(?)',('Testprojekt',))
 existing_projects=['Testprojekt']
if st.session_state.get('active_tga_project') not in existing_projects:
 st.session_state['active_tga_project']=existing_projects[0]
project=st.selectbox('Aktives Bauprojekt',existing_projects,index=existing_projects.index(st.session_state['active_tga_project']),key='tga_project_selector')
st.session_state['active_tga_project']=project
with st.expander('➕ Neues Bauprojekt anlegen'):
 with st.form('create_tga_project',clear_on_submit=True):
  new_project=st.text_input('Projektbezeichnung',placeholder='z. B. Neubau Schule Nord')
  create_project=st.form_submit_button('Projekt anlegen',type='primary')
 if create_project:
  new_project=new_project.strip()
  if not new_project: st.error('Bitte eine Projektbezeichnung eingeben.')
  elif new_project in existing_projects: st.warning('Dieses Projekt ist bereits vorhanden.')
  elif len(new_project)>100 or any(x in new_project for x in ('/','\\')) or new_project in ('.','..'):
   st.error('Bitte einen kürzeren Projektnamen ohne Schrägstriche verwenden.')
  else:
   with db() as project_db:
    project_db.execute('INSERT INTO projects(name) VALUES(?)',(new_project,))
   st.session_state['active_tga_project']=new_project
   st.success('Projekt angelegt.')
   st.rerun()
st.caption('Jedes Projekt hat eine eigene Komponentenliste und Dokumentenmappe. Bestehende Projektdaten bleiben erhalten.')
# v1.0.1: Gespeicherten Projektbestand sichtbar machen; Excel ist nur Import/Aktualisierung.
try:
 con_saved=db()
 saved_count=con_saved.execute('SELECT COUNT(*) FROM components WHERE project=?',(project,)).fetchone()[0]
 con_saved.close()
except Exception:
 saved_count=0
if saved_count:
 st.success(f'Gespeichertes Projekt geladen: {saved_count} Komponenten. Kein erneuter Excel-Upload nötig.')
 with st.expander('Excel-Datei importieren / Projektbestand aktualisieren'):
  st.warning('Achtung: Beim Übernehmen einer neuen Excel-Liste werden die bisherigen Produktzuordnungen und Dokumentverknüpfungen dieses Projekts ersetzt. Andere Projekte bleiben unverändert.')
  upload=st.file_uploader('Komponentenliste auswählen',type=['xlsx'],key=f'project_excel_update_{project}')
else:
 st.info('Für dieses Projekt ist noch keine Komponentenliste gespeichert. Bitte einmalig eine Excel-Datei importieren.')
 upload=st.file_uploader('Komponentenliste hochladen',type=['xlsx'],key=f'project_excel_initial_{project}')
if upload:
 try:
  df=read_excel(upload.getvalue()); df['Erkennung %']=df.apply(score,axis=1); df['Status']=df['Erkennung %'].map(status); st.success(f'{len(df)} Komponenten erkannt.'); st.dataframe(df,width='stretch',hide_index=True)
  if st.button('Komponenten in Projekt übernehmen',type='primary'):
   con=db(); old_ids=[x[0] for x in con.execute('SELECT id FROM components WHERE project=?',(project,)).fetchall()]
   for old_id in old_ids:
    con.execute('DELETE FROM documents WHERE component_id=?',(old_id,)); con.execute('DELETE FROM component_selections WHERE component_id=?',(old_id,)); con.execute('DELETE FROM component_application_groups WHERE component_id=?',(old_id,))
   con.execute('DELETE FROM components WHERE project=?',(project,))
   for _,r in df.iterrows(): con.execute('INSERT INTO components(project,manufacturer,product,article_no,confidence,status,docs_searched) VALUES(?,?,?,?,?,?,0)',(project,r.Hersteller,r.Bezeichnung,r.Artikelnummer,score(r),status(score(r))))
   con.commit(); st.success('Projekt gespeichert.'); st.rerun()
 except Exception as e:st.error(str(e))
con=db(); rows=con.execute('SELECT id,manufacturer,product,article_no,confidence,status,docs_searched FROM components WHERE project=? ORDER BY id',(project,)).fetchall()
if rows:
 st.divider(); st.subheader('📊 Projekt-Dokumentationsübersicht')
 # Die Übersicht trennt Produkterkennung bewusst vom Dokumentationsstand.
 overview=[]
 for ocid,om,op,oa,oconf,ostat,osearched in rows:
  odb=con.execute('SELECT priority,verified,local_path,download_status,project_confirmed FROM documents WHERE component_id=?',(ocid,)).fetchall()
  ooffline=sum(1 for _,_,opath,_,_ in odb if opath and os.path.exists(opath))
  oonline=sum(1 for prio,verified,opath,dstatus,_ in odb if prio=='Empfohlen' and verified and not (opath and os.path.exists(opath)))
  orecommended=sum(1 for prio,_,_,_,_ in odb if prio=='Empfohlen')
  ocheck=sum(1 for prio,_,_,_,confirmed in odb if prio in ['Anwendungsfall prüfen','Optional / Ausführung prüfen'] and not confirmed)
  docstatus=documentation_light(bool(osearched or ooffline),odb)
  selections=get_component_selections(con,ocid)
  overview.append({'Status':docstatus,'Hersteller':om,'Bauteil':op,'Verbaute Komponenten':', '.join(selections) if selections else '—','Artikelnummer':oa or '—','Erkennung %':oconf,'Produkterkennung':ostat,'Empfohlen':orecommended,'Offline-PDFs':ooffline,'Online-Nachweise':oonline,'Prüfen':ocheck})
 ovdf=pd.DataFrame(overview)
 total=len(overview); auto_ok=sum(1 for x in overview if x['Erkennung %']>=95); need_confirm=total-auto_ok
 searched=sum(1 for x in overview if not x['Status'].startswith('🔴')); offline=sum(x['Offline-PDFs'] for x in overview); online=sum(x['Online-Nachweise'] for x in overview); checks=sum(x['Prüfen'] for x in overview)
 k1,k2,k3,k4,k5=st.columns(5)
 k1.metric('Bauteile',total); k2.metric('≥95 % erkannt',auto_ok); k3.metric('Bestätigung nötig',need_confirm); k4.metric('Offline-PDFs',offline); k5.metric('Online-Nachweise',online)
 st.caption(f'Dokumentensuche ausgeführt: {searched} von {total} Bauteilen · offene fachliche Prüfungen: {checks}. Status: 🔴 noch nicht bearbeitet · 🟡 Prüfung/offene Unterlagen · 🟢 Dokumentation geklärt.')
 st.dataframe(ovdf,width='stretch',hide_index=True)
 st.divider()
st.subheader('📁 Offline-Dokumente dieses Projekts')
st.caption('Nur tatsächlich gespeicherte PDF-Dateien werden hier als offline verfügbar angezeigt. Online-Nachweise bleiben online.')
_offline_rows=con.execute("SELECT c.manufacturer,c.product,d.doc_type,d.title,d.local_path FROM documents d JOIN components c ON c.id=d.component_id WHERE c.project=? AND d.local_path IS NOT NULL AND d.local_path != '' ORDER BY c.manufacturer,c.product,d.doc_type",(project,)).fetchall()
_offline_valid=[(m,p,typ,title,path) for m,p,typ,title,path in _offline_rows if os.path.isfile(path)]
if not _offline_valid:
 st.info('Für dieses Projekt sind noch keine Offline-PDFs gespeichert.')
else:
 st.success(f'{len(_offline_valid)} Offline-PDF(s) für dieses Projekt vorhanden.')
 for _idx,(_m,_p,_typ,_title,_path) in enumerate(_offline_valid):
  _left,_right=st.columns([4,1])
  _left.write(f'**{_m} · {_p}** – {_typ}: {_title}')
  with open(_path,'rb') as _pdf:
   _right.download_button('PDF öffnen / speichern',data=_pdf.read(),file_name=Path(_path).name,mime='application/pdf',key=f'project_offline_{_idx}_{project}')
 st.divider(); st.subheader('Komponenten & Dokumentenmappen'); st.info('Automatisch freigeschaltet: TROX FK2-EU/TVE sowie ROCKWOOL 800/Conlit U. „Empfohlen“ ist eine regelbasierte Vorauswahl; Sonderausführungen und ROCKWOOL-Anwendbarkeitsnachweise müssen fachlich zum Einbau passen.')
 for cid,m,p,a,conf,stat,docs_searched in rows:
  with st.expander(f'{m} · {p}'+(f' · {a}' if a else '')+f' — {conf}%'):
   st.write(f'**Bewertung:** {stat}')
   manufacturer_product_name,name_confirmed=con.execute('SELECT manufacturer_product_name,product_name_confirmed FROM components WHERE id=?',(cid,)).fetchone()
   if is_rockwool_conlit(m,p):
    st.markdown('**Herstellerbezeichnung prüfen**')
    if name_confirmed and manufacturer_product_name==CONLIT_OFFICIAL_NAME:
     st.success(f'Bestätigte Herstellerbezeichnung: {CONLIT_OFFICIAL_NAME}')
     st.caption(f'Ursprünglicher Excel-Eintrag bleibt erhalten: „{p}“. Für Suche und Dokumentzuordnung wird die bestätigte Herstellerbezeichnung verwendet.')
     if st.button('↩️ Herstellerbezeichnung zurücksetzen',key=f'conlit-name-reset-{cid}'):
      con.execute('UPDATE components SET manufacturer_product_name="", product_name_confirmed=0, docs_searched=0 WHERE id=?',(cid,)); con.commit(); st.rerun()
    else:
     st.warning(f'Der Excel-Eintrag „{p}“ ist nicht die aktuelle vollständige Herstellerbezeichnung.')
     st.write(f'**Meinst du {CONLIT_OFFICIAL_NAME}?**')
     c_yes,c_no=st.columns(2)
     if c_yes.button('✓ Ja, diese Bezeichnung übernehmen',key=f'conlit-name-yes-{cid}',type='primary'):
      con.execute('UPDATE components SET manufacturer_product_name=?, product_name_confirmed=1, confidence=100, status=? WHERE id=?',(CONLIT_OFFICIAL_NAME,'Herstellerbezeichnung bestätigt',cid)); con.commit(); st.rerun()
     if c_no.button('Nein / anderes Produkt',key=f'conlit-name-no-{cid}'):
      con.execute('UPDATE components SET manufacturer_product_name="", product_name_confirmed=0 WHERE id=?',(cid,)); con.commit(); st.info('Bitte Produktbezeichnung bzw. Artikelnummer im Bestand klären. Die automatische Conlit-Zuordnung wird nicht als bestätigt behandelt.')
   if is_geberit_mapress_therm(m,p) and not a:
    st.markdown('**Geberit Mapress Therm · verbaute Systemkomponenten**')
    st.warning('„Mapress Therm“ ist ein System. In einem Projekt können mehrere Komponenten gleichzeitig verbaut sein. Bitte alle tatsächlich vorhandenen Dokumentgruppen markieren.')
    choices=['Systemrohr CrTi']+list(MAPRESS_THERM_FITTINGS)
    saved_sel=get_component_selections(con,cid)
    selected=st.multiselect('Welche Komponenten sind im Projekt verbaut?',choices,default=[x for x in saved_sel if x in choices],key=f'mapress-multi-{cid}')
    if selected:
     st.success('Ausgewählt: '+', '.join(selected))
     st.caption('Dimensionen werden weiterhin nur getrennt, wenn sie andere relevante Unterlagen benötigen. Für die Montage bleibt d108 als fachlicher Prüffall gekennzeichnet.')
     if set(selected)!=set(saved_sel):
      if st.button('✓ Auswahl im Projekt speichern',key=f'mapress-save-{cid}',type='primary'):
       save_component_selections(con,cid,selected); con.execute('UPDATE components SET docs_searched=0 WHERE id=?',(cid,)); con.commit(); st.rerun()
     else:
      st.info('Diese Mehrfachauswahl ist im Projekt gespeichert.')
      if st.button('🔎 Dokumente für alle ausgewählten Mapress-Komponenten suchen',key=f'mapress-docs-multi-{cid}',type='primary'):
       source,docs=mapress_selection_docs(selected); st.session_state[f'd-{cid}']=docs; st.session_state[f'q-{cid}']=source; persist_search_docs(con,cid,docs); st.rerun()
    else:
     st.caption('Noch keine Mapress-Systemkomponente ausgewählt. Beispiel: Systemrohr CrTi + Muffe können gleichzeitig markiert werden.')
     if saved_sel and st.button('Leere Auswahl speichern',key=f'mapress-clear-{cid}'):
      save_component_selections(con,cid,[]); con.execute('UPDATE components SET docs_searched=0 WHERE id=?',(cid,)); con.commit(); st.rerun()
    st.caption('Grundsatz: Mehrere tatsächlich verbaute Systemkomponenten dürfen gleichzeitig ausgewählt werden. Reine Dimensionsvarianten erzeugen nur bei dokumentrelevanten Unterschieden eigene Gruppen.')
   if is_geberit_verified(m,a):
    cfg=GEBERIT_VERIFIED_PRODUCTS[clean(a)]
    st.success(f"Geberit-Artikel exakt erkannt: {a} — {cfg['name']} · {cfg['details']}")
    if st.button('🔎 Geberit-Dokumente für exakten Artikel suchen',key=f'geberit-search-{cid}',type='primary'):
     source,docs=find_geberit_docs(a); st.session_state[f'd-{cid}']=docs; st.session_state[f'q-{cid}']=source; persist_search_docs(con,cid,docs)
     st.rerun()
   if is_grohe_eurosmart_ce(m,p):
    st.markdown('**GROHE-Variantenauflösung**')
    if a in GROHE_VARIANTS:
     st.success(f'Variante bestätigt: {grohe_variant_label(a)}')
     st.caption('Die konkrete Artikelnummer ist dem Bauteil zugeordnet. Die Dokumentensuche wird ausschließlich über diese Artikelnummer gestartet.')
     if st.button('🔎 GROHE-Dokumente für bestätigte Variante suchen',key=f'grohe-search-{cid}',type='primary'):
      try:
       with st.spinner(f'Offizielle GROHE-Produktseite für {a} wird ausgewertet …'): source,docs=find_grohe_docs(a)
       st.session_state[f'd-{cid}']=docs; st.session_state[f'q-{cid}']=source; persist_search_docs(con,cid,docs)
       st.rerun()
       if docs: st.success(f'{len(docs)} variantenspezifische Dokumente gefunden.')
       else: st.warning('Auf der offiziellen GROHE-Produktseite wurden noch keine eindeutig klassifizierbaren Dokumentlinks erkannt.')
      except Exception as e: st.error(str(e))
     if st.button('↩️ Variantenbestätigung zurücksetzen',key=f'grohe-reset-{cid}'):
      con.execute('UPDATE components SET article_no=?, confidence=?, status=? WHERE id=?',('',85,'Bestätigung empfohlen',cid)); con.commit(); st.rerun()
    else:
     st.warning('„Eurosmart CE“ ist eine Produktfamilie. Bitte die tatsächlich verbaute Variante bestätigen, bevor Dokumente zugeordnet werden.')
     options=['Bitte Variante auswählen …']+list(GROHE_VARIANTS)
     choice=st.selectbox('Variante / Artikelnummer',options,key=f'grohe-var-{cid}',format_func=lambda x: x if x.startswith('Bitte') else grohe_variant_label(x))
     if choice!='Bitte Variante auswählen …':
      st.info(GROHE_VARIANTS[choice]['details'])
      if choice=='36332000':
       st.link_button('Offizielle GROHE-Produktseite öffnen','https://www.grohe.de/de_de/eurosmart-ce-infrarot-elektronik-waschtisch-wandarmatur-mit-mischeinrichtung-und-thermostat-36332000.html')
      else:
       st.link_button('Artikelnummer bei GROHE suchen','https://www.google.com/search?q='+urllib.parse.quote(f'site:grohe.de Eurosmart CE {choice}'))
      if st.button('✓ Diese Variante bestätigen',key=f'grohe-confirm-{cid}',type='primary'):
       con.execute('UPDATE components SET article_no=?, confidence=?, status=? WHERE id=?',(choice,100,'Variante bestätigt',cid)); con.commit(); st.rerun()
    if a not in GROHE_VARIANTS: st.caption('Dokumente werden bewusst noch nicht geladen, solange keine konkrete GROHE-Variante bestätigt ist.')
   conlit_name_ok=(not is_rockwool_conlit(m,p)) or bool(name_confirmed and manufacturer_product_name==CONLIT_OFFICIAL_NAME)
   auto=(product_key(m,p) in PRODUCTS and conlit_name_ok) or (is_grohe_eurosmart_ce(m,p) and a in GROHE_VARIANTS) or is_geberit_verified(m,a) or is_geberit_mapress_therm(m,p)
   if auto:
    if not is_grohe_eurosmart_ce(m,p) and not is_geberit_verified(m,a) and not is_geberit_mapress_therm(m,p) and st.button(f'🔎 {m}-Dokumente automatisch suchen',key=f's-{cid}',type='primary'):
     try:
      with st.spinner(f'Offizielle {m}-Produktseite wird ausgewertet …'): source,docs=find_docs(m,p)
      st.session_state[f'd-{cid}']=docs; st.session_state[f'q-{cid}']=source; persist_search_docs(con,cid,docs)
      st.rerun()
      if docs:
       st.success(f'{len(docs)} mögliche Dokumente gefunden.')
      else:
       st.warning('Keine Dokumentlinks erkannt.')
     except Exception as e:st.error(str(e))
    docs=st.session_state.get(f'd-{cid}',[]); source=st.session_state.get(f'q-{cid}')
    if source: st.caption(f'Geprüfte Herstellerseite: {source} · erkannte Links: {len(docs)}')
    if docs:
     rel=[d for d in docs if d['Relevant']]
     recommended_diag=[d for d in rel if d['Priorität']=='Empfohlen']
     check_diag=[d for d in rel if d['Priorität'] in ['Anwendungsfall prüfen','Optional / Ausführung prüfen']]
     optional_diag=[d for d in rel if d['Priorität']=='Optional']
     st.caption(f"Diagnose: {len(docs)} akzeptierte Herstellerlinks · {len(rel)} produktrelevant · {len(recommended_diag)} empfohlen · {len(check_diag)} prüfen · {len(optional_diag)} optional")
     st.markdown(f'**Relevante Produktdokumente: {len(rel)} von {len(docs)} Treffern**')
     if rel:
      rdf=pd.DataFrame(rel); st.dataframe(rdf[['Kategorie','Priorität','Titel','Resolver','Treffer %','URL']],width='stretch',hide_index=True)
      recommended=[d for d in rel if d['Priorität']=='Empfohlen']
      downloadable_recommended=[d for d in recommended if d.get('Downloadbar',True)]
      online_evidence=[d for d in recommended if not d.get('Downloadbar',True)]
      st.write(f'**Standardmappe:** {len(recommended)} Dokument(e) als „Empfohlen“ markiert · {len(downloadable_recommended)} als Offline-PDF · {len(online_evidence)} als verifizierter Online-Nachweis.')
      if product_key(m,p)[1]=='CONLIT U': st.info('Conlit 150 U: produktbezogener Verwendbarkeitsnachweis laut ROCKWOOL: abP P-NDS04-417. Der generische DoP-Link wird deshalb nicht als empfohlenes Produktdokument gewertet.')
      for ev in online_evidence:
       if ev.get('Nachweis URL'):
        st.info(f"{ev['Titel']}: verifizierter Online-Nachweis (kein Offline-PDF-Download wird vorgetäuscht).")
        st.link_button(f"Nachweis öffnen: {ev['Titel']}",ev['Nachweis URL'],key=f"ev-{cid}-{hashlib.sha1(ev['Titel'].encode()).hexdigest()[:8]}")
      c1,c2=st.columns(2)
      if c1.button('⬇️ Empfohlene PDFs offline speichern',key=f'dlr-{cid}',type='primary',disabled=not downloadable_recommended):
       todo=downloadable_recommended; ok=0; errs=[]
       for d in todo:
        try:
         path,size,resolved_url=download(project,m,p,d); con.execute('DELETE FROM documents WHERE component_id=? AND source_url=? AND title=?',(cid,d['URL'],d['Titel'])); con.execute('INSERT INTO documents(component_id,doc_type,title,source_url,verified,confidence,source_page,local_path,download_status,priority) VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,d['Kategorie'],d['Titel'],d['URL'],0,d['Treffer %'],d['Quellseite'],path,f'Offline · {size/1024/1024:.1f} MB',d['Priorität'])); ok+=1
        except Exception as e:errs.append(f"{d['Titel']}: {e}")
       con.commit(); st.session_state[f'download-report-{cid}']={'ok':ok,'errs':errs,'kind':'empfohlen'}; st.rerun()
      if c2.button('⬇️ Alle relevanten PDFs offline speichern',key=f'dla-{cid}',disabled=not rel):
       ok=0; errs=[]
       for d in [x for x in rel if x.get('Downloadbar',True)]:
        try:
         path,size,resolved_url=download(project,m,p,d); con.execute('DELETE FROM documents WHERE component_id=? AND source_url=? AND title=?',(cid,d['URL'],d['Titel'])); con.execute('INSERT INTO documents(component_id,doc_type,title,source_url,verified,confidence,source_page,local_path,download_status,priority) VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,d['Kategorie'],d['Titel'],d['URL'],0,d['Treffer %'],d['Quellseite'],path,f'Offline · {size/1024/1024:.1f} MB',d['Priorität'])); ok+=1
        except Exception as e:errs.append(f"{d['Titel']}: {e}")
       con.commit(); st.session_state[f'download-report-{cid}']={'ok':ok,'errs':errs,'kind':'alle relevanten'}; st.rerun()
     with st.expander('Alle erkannten Herstellerlinks'): st.dataframe(pd.DataFrame(docs)[['Kategorie','Priorität','Titel','Resolver','Treffer %','URL']],width='stretch',hide_index=True)
   elif not is_grohe_eurosmart_ce(m,p):
    st.caption('Automatische Herstellersuche für dieses Produkt noch nicht aktiviert.'); st.link_button('Herstellerbezogene Produktsuche öffnen',google_url(m,p,a))
   report=st.session_state.get(f'download-report-{cid}')
   if report:
    st.success(f"{report['ok']} PDF(s) erfolgreich offline gespeichert.")
    if report['errs']:
     st.warning(f"{len(report['errs'])} Download(s) fehlgeschlagen.")
     for msg in report['errs']: st.caption(msg)
   for _fkcode in ['fk2_atex','fk2_special_mounting']:
    _fkr=st.session_state.get(f'fk2-group-report-{cid}-{_fkcode}')
    if _fkr:
     if _fkr['ok']==_fkr['total'] and not _fkr['errs']: st.success(f"{_fkr['ok']} von {_fkr['total']} benötigten {FK2_APPLICATION_GROUPS[_fkcode]}-Dokumenten offline gespeichert/verifiziert.")
     else:
      st.warning(f"{_fkr['ok']} von {_fkr['total']} benötigten {FK2_APPLICATION_GROUPS[_fkcode]}-Dokumenten konnten offline gespeichert/verifiziert werden.")
      for _msg in _fkr['errs']: st.caption(_msg)
   conlit_report=st.session_state.get(f'conlit-proof-report-{cid}')
   if conlit_report:
    if conlit_report['ok']==conlit_report['total'] and not conlit_report['errs']: st.success(f"{conlit_report['ok']} Conlit-Nachweis(e) automatisch zugeordnet und offline gespeichert.")
    else:
     st.warning(f"{conlit_report['ok']} von {conlit_report['total']} Conlit-Nachweisen konnten automatisch offline gespeichert werden.")
     for msg in conlit_report['errs']: st.caption(msg)
   saved=con.execute('SELECT id,doc_type,title,source_url,confidence,local_path,download_status,priority,project_confirmed,source_page,project_decision,project_decision_note FROM documents WHERE component_id=? ORDER BY priority,doc_type,title',(cid,)).fetchall()
   if saved and is_trox_fk2(m,p):
    fk2_saved_groups=get_application_groups(con,cid)
    if 'fk2_standard' in fk2_saved_groups:
     selected_extra=[x for x in fk2_saved_groups if x in ['fk2_atex','fk2_special_mounting']]
     save_fk2_application(con,cid,selected_extra,saved)
     saved=con.execute('SELECT id,doc_type,title,source_url,confidence,local_path,download_status,priority,project_confirmed,source_page,project_decision,project_decision_note FROM documents WHERE component_id=? ORDER BY priority,doc_type,title',(cid,)).fetchall()
   if saved:
    st.markdown('**Dokumentenmappe**')
    for docid,dtype,title,url,dconf,path,dstatus,prio,confirmed,source_page,decision,decision_note in saved:
     exists=bool(path and os.path.exists(path)); c1,c2,c3=st.columns([4,1,1]); c1.write(f'**{dtype}** · {title}'); c1.caption(prio or ''); c2.write('✅ Offline' if exists else ('🌐 Online' if dstatus=='Online-Nachweis' else '⚠️ Fundstelle'))
     if exists:
      with open(path,'rb') as fh:c3.download_button('PDF öffnen',data=fh.read(),file_name=os.path.basename(path),mime='application/pdf',key=f'p-{cid}-{docid}')
     elif url:c3.link_button('Quelle',url)
    if is_trox_fk2(m,p):
     st.markdown('### 🧭 FK2-EU · Anwendung festlegen')
     st.caption('Standardunterlagen gelten immer. Zusätzliche Auswahlmöglichkeiten erscheinen nur für Anwendungen, die andere Dokumentgruppen benötigen.')
     saved_groups=get_application_groups(con,cid)
     selected_labels=[]
     if 'fk2_atex' in saved_groups: selected_labels.append(FK2_APPLICATION_GROUPS['fk2_atex'])
     if 'fk2_special_mounting' in saved_groups: selected_labels.append(FK2_APPLICATION_GROUPS['fk2_special_mounting'])
     options=[FK2_APPLICATION_GROUPS['fk2_atex'],FK2_APPLICATION_GROUPS['fk2_special_mounting']]
     choices=st.multiselect('Welche zusätzlichen Sonderanwendungen kommen in diesem Projekt vor?',options,default=selected_labels,key=f'fk2-app-{cid}')
     st.write('**Standardanwendung / Standarddokumentation ist immer die Basis.**')
     if not choices: st.info('Keine zusätzliche Sonderanwendung ausgewählt. ATEX- und Sondermontage-Unterlagen werden für dieses Projekt nicht als Pflichtunterlagen gewertet.')
     else:
      if FK2_APPLICATION_GROUPS['fk2_atex'] in choices: st.write('• ATEX → die zusammengehörige ATEX-Dokumentgruppe wird benötigt (nicht vier getrennte Projektentscheidungen).')
      if FK2_APPLICATION_GROUPS['fk2_special_mounting'] in choices: st.write('• Montage-Sonderanwendung → die zusätzliche Sondermontage-Dokumentgruppe wird benötigt.')
     if st.button('FK2-EU Anwendung speichern',key=f'fk2-app-save-{cid}',type='primary'):
      codes=[]
      if FK2_APPLICATION_GROUPS['fk2_atex'] in choices: codes.append('fk2_atex')
      if FK2_APPLICATION_GROUPS['fk2_special_mounting'] in choices: codes.append('fk2_special_mounting')
      save_fk2_application(con,cid,codes,saved); st.rerun()
     for code in ['fk2_atex','fk2_special_mounting']:
      if code in saved_groups:
       group_rows=[r for r in saved if fk2_check_group(r[1])==code]
       complete=fk2_group_complete(saved,code)
       if complete: st.success(f"{FK2_APPLICATION_GROUPS[code]}: benötigte Dokumentgruppe vorhanden.")
       else:
        st.warning(f"{FK2_APPLICATION_GROUPS[code]}: ausgewählt, aber die benötigten PDF-Unterlagen sind noch nicht vollständig offline gespeichert/verifiziert.")
        required_rows=fk2_required_group_rows(saved,code)
        if required_rows:
         st.caption('Benötigte aktuelle Dokumente: ' + ' · '.join(r[2] for r in required_rows))
         if st.button(f'⬇️ {FK2_APPLICATION_GROUPS[code]} gezielt offline speichern',key=f'fk2-group-dl-{cid}-{code}'):
          ok=0; errs=[]
          for rr in required_rows:
           rdocid,rdtype,rtitle,rurl,rdconf,rpath,rdstatus,rprio,rconfirmed,rsource,rdecision,rnote=rr
           if (rpath and os.path.exists(rpath)) or rdstatus=='Online-Nachweis':
            ok+=1; continue
           d={'Kategorie':rdtype,'Titel':rtitle,'URL':rurl,'Treffer %':rdconf,'Quellseite':rsource,'Priorität':rprio}
           try:
            path,size,resolved_url=download(project,m,p,d)
            con.execute('UPDATE documents SET local_path=?,download_status=?,verified=1 WHERE id=?',(path,f'Offline · {size/1024/1024:.1f} MB',rdocid)); ok+=1
           except Exception as e: errs.append(f'{rtitle}: {e}')
          con.commit()
          refreshed=con.execute('SELECT id,doc_type,title,source_url,confidence,local_path,download_status,priority,project_confirmed,source_page,project_decision,project_decision_note FROM documents WHERE component_id=? ORDER BY priority,doc_type,title',(cid,)).fetchall()
          selected_now=[x for x in get_application_groups(con,cid) if x in ['fk2_atex','fk2_special_mounting']]
          save_fk2_application(con,cid,selected_now,refreshed)
          st.session_state[f'fk2-group-report-{cid}-{code}']={'ok':ok,'total':len(required_rows),'errs':errs}
          st.rerun()
        else:
         st.error('Für diese Zusatzgruppe wurde noch kein passender Hersteller-Nachweis erkannt. Bitte Herstellersuche erneut ausführen.')
    open_checks=[d for d in saved if d[7] in ['Anwendungsfall prüfen','Optional / Ausführung prüfen'] and not d[8] and not (is_trox_fk2(m,p) and fk2_check_group(d[1]))]
    confirmed_checks=[d for d in saved if d[7] in ['Anwendungsfall prüfen','Optional / Ausführung prüfen'] and d[8] and not (is_trox_fk2(m,p) and fk2_check_group(d[1]))]
    if open_checks:
     st.markdown('### ⚠️ Offene Projektprüfungen')
     st.caption('Diese Punkte benötigen eine fachliche Entscheidung für genau dieses Projekt. Die Herstellerquelle bleibt davon unverändert.')
     for docid,dtype,title,url,dconf,path,dstatus,prio,confirmed,source_page,decision,decision_note in open_checks:
      st.warning(f'**{dtype}: {title}**')
      if source_page: st.caption(source_page)
      is_mapress_install=('mapress therm' in clean(p).lower() and 'installation / verarbeitung' in clean(title).lower())
      is_rockwool800_proof=('rockwool' in clean(m).lower() and product_key(m,p)[1]=='800' and dtype=='Zulassung / Prüfzeugnis' and 'anwendbarkeitsnachweise' in clean(title).lower())
      is_conlit_proof=(is_rockwool_conlit(m,p) and dtype=='Zulassung / Prüfzeugnis' and 'anwendbarkeitsnachweise' in clean(title).lower())
      if is_mapress_install:
       st.write('**Geführte Prüfung:** Geberit weist für d108 eine abweichende Verarbeitung aus. Welche Dimensionen sind in diesem Projekt verbaut?')
       options=['Noch nicht bekannt','Nur d12–d88,9','d108 ist ebenfalls verbaut']
       prior={'mapress_unknown':'Noch nicht bekannt','mapress_no_d108':'Nur d12–d88,9','mapress_d108':'d108 ist ebenfalls verbaut'}.get(decision,'Noch nicht bekannt')
       choice=st.radio('Dimensionen im Projekt',options,index=options.index(prior),key=f'guided-{cid}-{docid}')
       if choice=='Nur d12–d88,9':
        st.info('Der d108-Sonderfall betrifft dieses Projekt damit nicht. Diese Prüfung kann abgeschlossen werden.')
       elif choice=='d108 ist ebenfalls verbaut':
        st.warning('d108 ist verbaut. Die Prüfung bleibt offen, bis die d108-spezifische Verarbeitung bzw. passende Unterlage eindeutig abgesichert ist.')
       else:
        st.info('Solange die Dimensionen nicht bekannt sind, bleibt die Prüfung offen.')
       if st.button('Prüfentscheidung speichern',key=f'guided-save-{cid}-{docid}',type='primary'):
        if choice=='Nur d12–d88,9': code='mapress_no_d108'; note='Im Projekt sind nur d12–d88,9 verbaut; der d108-Sonderfall ist nicht relevant.'; conf=1
        elif choice=='d108 ist ebenfalls verbaut': code='mapress_d108'; note='d108 ist im Projekt verbaut; d108-spezifische Verarbeitung/Unterlage ist noch abzusichern.'; conf=0
        else: code='mapress_unknown'; note='Verbaute Dimensionen sind noch nicht bekannt.'; conf=0
        con.execute('UPDATE documents SET project_confirmed=?,project_decision=?,project_decision_note=? WHERE id=?',(conf,code,note,docid)); con.commit(); st.rerun()
      elif is_rockwool800_proof:
       st.write('**Geführte Einbausituationsprüfung:** Wie wird ROCKWOOL 800 in diesem Projekt eingesetzt?')
       options=['Noch nicht bekannt','Normale technische Rohrdämmung – keine brandschutztechnische Funktion','Teil einer brandschutztechnischen Konstruktion / Abschottung / Durchführung','Andere oder gemischte Einbausituation']
       prior={'rw800_unknown':options[0],'rw800_standard':options[1],'rw800_fire':options[2],'rw800_other':options[3]}.get(decision,options[0])
       choice=st.radio('Einbausituation',options,index=options.index(prior),key=f'rw800-guided-{cid}-{docid}')
       if choice==options[1]:
        st.info('Für diese Projektangabe wird der allgemeine Prüfhaken „Anwendbarkeitsnachweise“ nicht als zusätzlich offener Standardnachweis behandelt. Die vorhandene Standardmappe bleibt maßgeblich.')
       elif choice==options[2]:
        st.warning('Brandschutztechnische Anwendung angegeben. Die Prüfung bleibt offen: Die konkrete Konstruktion, Bauteil-/Durchführungssituation und der dafür geltende Nachweis müssen projektbezogen zugeordnet werden.')
       elif choice==options[3]:
        st.warning('Die Einbausituation ist nicht eindeutig einer Standardanwendung zuzuordnen. Die Prüfung bleibt offen, bis die konkrete Anwendung geklärt ist.')
       else:
        st.info('Solange die Einbausituation nicht bekannt ist, bleibt die Prüfung offen.')
       if st.button('Einbausituation speichern',key=f'rw800-guided-save-{cid}-{docid}',type='primary'):
        if choice==options[1]: code='rw800_standard'; note='Normale technische Rohrdämmung ohne brandschutztechnische Funktion angegeben; allgemeiner Anwendbarkeits-Prüfhaken für dieses Projekt abgeschlossen.'; conf=1
        elif choice==options[2]: code='rw800_fire'; note='Brandschutztechnische Konstruktion/Abschottung/Durchführung angegeben; konkreter projektbezogener Nachweis ist noch zu klären.'; conf=0
        elif choice==options[3]: code='rw800_other'; note='Andere oder gemischte Einbausituation angegeben; konkrete Anwendung und Nachweisbedarf sind noch zu klären.'; conf=0
        else: code='rw800_unknown'; note='Einbausituation von ROCKWOOL 800 ist noch nicht bekannt.'; conf=0
        con.execute('UPDATE documents SET project_confirmed=?,project_decision=?,project_decision_note=? WHERE id=?',(conf,code,note,docid)); con.commit(); st.rerun()
      elif is_conlit_proof:
       st.write('**Geführte Einbausituationsprüfung für Conlit® 150 U**')
       st.caption('Mehrfachauswahl: Es werden nur Gruppen getrennt, wenn unterschiedliche relevante Nachweise gelten. Reine Varianten mit gleicher Dokumentation werden zusammengefasst.')
       labels=list(CONLIT_DOCUMENT_GROUPS)
       saved_codes=get_application_groups(con,cid)
       defaults=[label for label,cfg in CONLIT_DOCUMENT_GROUPS.items() if cfg['code'] in saved_codes]
       choices=st.multiselect('Welche dokumentationsrelevanten Einbausituationen kommen in diesem Projekt vor?',labels,default=defaults,key=f'conlit-multi-{cid}-{docid}')
       unknown=st.checkbox('Einbausituation noch nicht vollständig bekannt / weitere Situation möglich',value=(decision in ['conlit_unknown','conlit_other']),key=f'conlit-unknown-{cid}-{docid}')
       if choices:
        st.markdown('**Dafür werden folgende Hersteller-Nachweise benötigt:**')
        for label in choices:
         cfg=CONLIT_DOCUMENT_GROUPS[label]; st.write(f"• {label} → **{cfg['proof']}**")
       if unknown: st.warning('Solange weitere Einbausituationen möglich oder unbekannt sind, bleibt die Prüfung 🟡.')
       elif not choices: st.info('Bitte mindestens eine tatsächlich verbaute, dokumentationsrelevante Einbausituation auswählen.')
       else: st.info('Beim Speichern ordnet die App jeder Auswahl den offiziellen ROCKWOOL-Nachweis zu und versucht, die PDF direkt offline zu sichern.')
       if st.button('Einbausituationen speichern & Nachweise zuordnen',key=f'conlit-guided-save-{cid}-{docid}',type='primary'):
        codes=[CONLIT_DOCUMENT_GROUPS[x]['code'] for x in choices]; save_application_groups(con,cid,codes)
        if unknown or not choices:
         code='conlit_unknown' if not choices else 'conlit_other'; note='Einbausituation ist noch nicht vollständig bekannt.'; conf=0
         con.execute('UPDATE documents SET project_confirmed=?,project_decision=?,project_decision_note=? WHERE id=?',(conf,code,note,docid)); con.commit(); st.rerun()
        ok,errs=ensure_conlit_proofs(con,project,cid,m,p,choices)
        all_ok=(len(ok)==len(choices) and not errs)
        code='conlit_multi_complete' if all_ok else 'conlit_multi_open'
        note='Ausgewählte Dokumentgruppen: '+', '.join(CONLIT_DOCUMENT_GROUPS[x]['proof'] for x in choices)+('. Alle offiziellen Nachweise wurden offline zugeordnet.' if all_ok else '. Mindestens ein Nachweis konnte noch nicht offline verifiziert/zugeordnet werden.')
        con.execute('UPDATE documents SET project_confirmed=?,project_decision=?,project_decision_note=? WHERE id=?',(1 if all_ok else 0,code,note,docid)); con.commit()
        st.session_state[f'conlit-proof-report-{cid}']={'ok':len(ok),'total':len(choices),'errs':errs}; st.rerun()
      else:
       st.info('Für diesen Prüffall gibt es noch keine geführte Einbausituationsprüfung. Bitte nicht blind bestätigen; der konkrete Anwendungsfall sollte zuerst geklärt werden.')
    if confirmed_checks:
     st.markdown('### ✅ Bestätigte Projektprüfungen')
     for docid,dtype,title,url,dconf,path,dstatus,prio,confirmed,source_page,decision,decision_note in confirmed_checks:
      st.success(f'**{dtype}: {title}** · für dieses Projekt fachlich geprüft und bestätigt')
      if decision_note: st.caption(f'Prüfentscheidung: {decision_note}')
      if st.button('Prüfentscheidung zurücknehmen / ändern',key=f'unconfirm-{cid}-{docid}'):
       con.execute('UPDATE documents SET project_confirmed=0,project_decision="",project_decision_note="" WHERE id=?',(docid,)); con.commit(); st.rerun()


# v1.3.9: dauerhafter Update-Installationsbereich.
# Der Downloadpfad wird unabhängig vom Download-Button auf jeder Streamlit-Ausführung geprüft.
_update_package = st.session_state.get("downloaded_update_path")
if _update_package:
    _update_package_path = Path(_update_package)
    if _update_package_path.exists():
        st.sidebar.markdown("---")
        st.sidebar.success("Update vollständig heruntergeladen und geprüft.")
        st.sidebar.caption(f"Update-Paket: {_update_package_path}")
        if st.button(
            "Update jetzt installieren",
            key="persistent_update_install_v150",
            type="primary",
            use_container_width=True,
        ):
            try:
                _started = install_downloaded_update(_update_package_path)
                st.sidebar.success("Windows-Updater wurde direkt gestartet.")
                st.sidebar.info("Bitte das geöffnete Update-Fenster nicht schließen. Die App wird anschließend neu gestartet.")
            except Exception as exc:
                st.sidebar.error(f"Update konnte nicht gestartet werden: {exc}")
    else:
        st.session_state.pop("downloaded_update_path", None)

