"""Persistent company/source memory; inferred ownership stays explicitly unverified."""
import hashlib
import json
import sqlite3
from contextlib import closing
from urllib.parse import urlsplit
from .sources import normalized

ATS={"greenhouse.io":"Greenhouse","lever.co":"Lever","ashbyhq.com":"Ashby","personio.de":"Personio","personio.com":"Personio","recruitee.com":"Recruitee","smartrecruiters.com":"SmartRecruiters","myworkdayjobs.com":"Workday"}

def source_info(url):
    url=normalized(url);host=urlsplit(url).hostname
    ats=next((name for domain,name in ATS.items() if host==domain or host.endswith('.'+domain)),None)
    return {"url":url,"host":host,"ats":ats,"official_status":"unverified"}

class Registry:
    def __init__(self,path):
        path.parent.mkdir(parents=True,exist_ok=True);self.path=path
        with closing(sqlite3.connect(path)) as db,db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS corroborations(id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE IF NOT EXISTS company_profiles(id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE IF NOT EXISTS official_edges(origin TEXT,target TEXT,PRIMARY KEY(origin,target));
            CREATE TABLE IF NOT EXISTS board_counts(url TEXT,run_id TEXT,payload TEXT,PRIMARY KEY(url,run_id));
            CREATE TABLE IF NOT EXISTS competitor_leads(id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE IF NOT EXISTS signal_cursor(id INTEGER PRIMARY KEY,value INTEGER);
            CREATE TABLE IF NOT EXISTS signals(id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE IF NOT EXISTS assessments(url TEXT, content_hash TEXT, context_hash TEXT, payload TEXT, PRIMARY KEY(url,content_hash,context_hash));
            CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY,name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources(url TEXT PRIMARY KEY,host TEXT,ats TEXT);
            CREATE TABLE IF NOT EXISTS company_sources(company_id TEXT,url TEXT,run_id TEXT,PRIMARY KEY(company_id,url,run_id));
            CREATE TABLE IF NOT EXISTS source_observations(url TEXT,run_id TEXT,observed_at TEXT,status TEXT,content_hash TEXT,http_status INTEGER,PRIMARY KEY(url,run_id));
            """)
    def save_corroboration(self,item):
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('INSERT OR REPLACE INTO corroborations VALUES(?,?)',(item['id'],json.dumps(item)))
    def configure_profiles(self,profiles):
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('DELETE FROM company_profiles')
            for profile in profiles:
                data=profile.model_dump() if hasattr(profile,'model_dump') else profile
                ident=hashlib.sha256(data['name'].casefold().encode()).hexdigest()[:24]
                db.execute('INSERT INTO company_profiles VALUES(?,?)',(ident,json.dumps(data)))
                db.execute('INSERT OR IGNORE INTO companies VALUES(?,?)',(ident,data['name']))
                names={' '.join(n.split()).casefold() for n in [data['name'],*data['aliases']]}
                for old_id,old_name in db.execute('SELECT id,name FROM companies').fetchall():
                    if old_id!=ident and ' '.join(old_name.split()).casefold() in names:
                        db.execute('INSERT OR IGNORE INTO company_sources SELECT ?,url,run_id FROM company_sources WHERE company_id=?',(ident,old_id))
                        db.execute('DELETE FROM company_sources WHERE company_id=?',(old_id,));db.execute('DELETE FROM companies WHERE id=?',(old_id,))
    def canonical_name(self,name):
        with closing(sqlite3.connect(self.path)) as db:
            for payload, in db.execute('SELECT payload FROM company_profiles'):
                profile=json.loads(payload)
                if ' '.join(name.split()).casefold() in {' '.join(n.split()).casefold() for n in [profile['name'],*profile['aliases']]}:return profile['name']
        return name
    def ingest(self,run_id,findings,records):
        with closing(sqlite3.connect(self.path)) as db,db:
            for raw,record in records.items():
                if record.get('http_status')==200:
                    for link in record.get('links',[]):db.execute('INSERT OR IGNORE INTO official_edges VALUES(?,?)',(raw,link))
                try: info=source_info(raw)
                except ValueError: continue
                if record.get('structured_index') and isinstance(record.get('returned_count'),int):
                    metrics={k:record.get(k) for k in ('observed_at','ats_provider','ats_tenant','returned_count','reported_total')}
                    db.execute('INSERT OR IGNORE INTO board_counts VALUES(?,?,?)',(info['url'],run_id,json.dumps(metrics)))
                url=info['url'];db.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?)",(url,info['host'],info['ats']))
                ok=record.get('http_status')==200
                status='closed_marker' if ok and record.get('closed_marker') else 'retrieved' if ok else 'unavailable'
                digest=hashlib.sha256(record.get('text','').encode()).hexdigest() if ok else None
                db.execute("INSERT OR IGNORE INTO source_observations VALUES(?,?,?,?,?,?)",(url,run_id,record.get('observed_at'),status,digest,record.get('http_status')))
            for finding in findings:
                name=self.canonical_name(' '.join(finding.get('company','').split()))
                if not name or name.casefold() in ('unknown','n/a'): continue
                try: info=source_info(finding['url'])
                except (ValueError,KeyError): continue
                ident=hashlib.sha256(name.casefold().encode()).hexdigest()[:24]
                db.execute("INSERT OR IGNORE INTO companies VALUES(?,?)",(ident,name))
                db.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?)",(info['url'],info['host'],info['ats']))
                db.execute("INSERT OR IGNORE INTO company_sources VALUES(?,?,?)",(ident,info['url'],run_id))
    def ingest_competitors(self,leads):
        with closing(sqlite3.connect(self.path)) as db,db:
            for lead in leads:
                ident=hashlib.sha256(json.dumps([lead[k] for k in ('seed_company','company','url')]).encode()).hexdigest()[:24]
                db.execute('INSERT OR REPLACE INTO competitor_leads VALUES(?,?)',(ident,json.dumps(lead)))
    def momentum(self):
        from .momentum import summarize
        with closing(sqlite3.connect(self.path)) as db:
            return [{'url':url,**summarize([json.loads(p) for p, in db.execute('SELECT payload FROM board_counts WHERE url=?',(url,))])} for url, in db.execute('SELECT DISTINCT url FROM board_counts')]
    def signal_offset(self,advance=0):
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("INSERT OR IGNORE INTO signal_cursor VALUES(1,0)")
            value=db.execute("SELECT value FROM signal_cursor WHERE id=1").fetchone()[0]
            if advance:db.execute("UPDATE signal_cursor SET value=value+? WHERE id=1",(advance,))
            return value
    def ingest_signals(self,signals):
        with closing(sqlite3.connect(self.path)) as db,db:
            for signal in signals:
                ident=hashlib.sha256(json.dumps([signal[k] for k in ('url','company','kind','title')]).encode()).hexdigest()[:24]
                db.execute("INSERT OR REPLACE INTO signals VALUES(?,?)",(ident,json.dumps(signal)))
        for signal in signals:self.ingest(signal['run_id'],[signal],{})
    def export(self):
        with closing(sqlite3.connect(self.path)) as db:
            companies=[{'id':i,'name':n,'identity_basis':'normalized_name_unverified','sources':[x[0] for x in db.execute('SELECT DISTINCT url FROM company_sources WHERE company_id=?',(i,))]} for i,n in db.execute('SELECT id,name FROM companies ORDER BY name')]
            from .qualification import qualify
            profiles={i:json.loads(p) for i,p in db.execute('SELECT id,payload FROM company_profiles')}
            edges=db.execute('SELECT origin,target FROM official_edges').fetchall()
            for company in companies:
                profile=profiles.get(company['id'])
                company['aliases']=profile['aliases'] if profile else []
                company['official_domains']=profile['official_domains'] if profile else []
                company['identity_basis']='user_configured' if profile else 'normalized_name_unverified'
                company['source_evidence']=[{'url':url,**(qualify(url,profile,edges) if profile else {'status':'unverified','basis':'No company profile configured'})} for url in company['sources']]
            sources=[]
            for url,host,ats in db.execute('SELECT url,host,ats FROM sources ORDER BY url'):
                history=[{'run_id':r,'observed_at':t,'status':s,'content_hash':h,'http_status':code} for r,t,s,h,code in db.execute('SELECT run_id,observed_at,status,content_hash,http_status FROM source_observations WHERE url=? ORDER BY observed_at,run_id',(url,))]
                previous=None
                for item in history:
                    item['change']='unknown'
                    if item['content_hash']:
                        item['change']='first_observation' if previous is None else 'unchanged' if previous==item['content_hash'] else 'text_changed'
                        previous=item['content_hash']
                sources.append({'url':url,'host':host,'ats':ats,'official_status':'unverified','history':history[-20:]})
            return {'companies':companies,'sources':sources,'corroborations':[json.loads(p) for p, in db.execute('SELECT payload FROM corroborations')],'momentum':self.momentum(),'competitors':[dict(json.loads(p),id=i) for i,p in db.execute('SELECT id,payload FROM competitor_leads')],'signals':[dict(json.loads(p),id=i) for i,p in db.execute('SELECT id,payload FROM signals')]}
    def monitor_targets(self,limit):
        with closing(sqlite3.connect(self.path)) as db:
            return [r[0] for r in db.execute("SELECT s.url FROM sources s LEFT JOIN source_observations o ON s.url=o.url GROUP BY s.url ORDER BY MAX(o.observed_at) ASC,s.url LIMIT ?",(limit,))]
    def cached_assessment(self,url,text,context_hash):
        digest=hashlib.sha256(text.encode()).hexdigest()
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute("SELECT payload FROM assessments WHERE url=? AND content_hash=? AND context_hash=?",(url,digest,context_hash)).fetchone()
            return json.loads(row[0]) if row else None
    def save_assessment(self,url,text,context_hash,payload):
        digest=hashlib.sha256(text.encode()).hexdigest()
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("INSERT OR REPLACE INTO assessments VALUES(?,?,?,?)",(url,digest,context_hash,json.dumps(payload)))
    def import_runs(self,root):
        for checkpoint in root.glob('*/checkpoint.json'):
            state=json.loads(checkpoint.read_text(encoding='utf-8'))
            self.ingest(checkpoint.parent.name,state.get('findings',[]),state.get('sources',{}))
            self.ingest_signals(state.get('signals',[]))
            self.ingest_competitors(state.get('competitor_leads',[]))
