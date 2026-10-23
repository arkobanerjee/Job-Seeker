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
            CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY,name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources(url TEXT PRIMARY KEY,host TEXT,ats TEXT);
            CREATE TABLE IF NOT EXISTS company_sources(company_id TEXT,url TEXT,run_id TEXT,PRIMARY KEY(company_id,url,run_id));
            CREATE TABLE IF NOT EXISTS source_observations(url TEXT,run_id TEXT,observed_at TEXT,status TEXT,content_hash TEXT,http_status INTEGER,PRIMARY KEY(url,run_id));
            """)
    def ingest(self,run_id,findings,records):
        with closing(sqlite3.connect(self.path)) as db,db:
            for raw,record in records.items():
                try: info=source_info(raw)
                except ValueError: continue
                url=info['url'];db.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?)",(url,info['host'],info['ats']))
                ok=record.get('http_status')==200
                status='closed_marker' if ok and record.get('closed_marker') else 'retrieved' if ok else 'unavailable'
                digest=hashlib.sha256(record.get('text','').encode()).hexdigest() if ok else None
                db.execute("INSERT OR IGNORE INTO source_observations VALUES(?,?,?,?,?,?)",(url,run_id,record.get('observed_at'),status,digest,record.get('http_status')))
            for finding in findings:
                name=' '.join(finding.get('company','').split())
                if not name or name.casefold() in ('unknown','n/a'): continue
                try: info=source_info(finding['url'])
                except (ValueError,KeyError): continue
                ident=hashlib.sha256(name.casefold().encode()).hexdigest()[:24]
                db.execute("INSERT OR IGNORE INTO companies VALUES(?,?)",(ident,name))
                db.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?)",(info['url'],info['host'],info['ats']))
                db.execute("INSERT OR IGNORE INTO company_sources VALUES(?,?,?)",(ident,info['url'],run_id))
    def export(self):
        with closing(sqlite3.connect(self.path)) as db:
            companies=[{'id':i,'name':n,'identity_basis':'normalized_name_unverified','sources':[x[0] for x in db.execute('SELECT DISTINCT url FROM company_sources WHERE company_id=?',(i,))]} for i,n in db.execute('SELECT id,name FROM companies ORDER BY name')]
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
            return {'companies':companies,'sources':sources}
    def import_runs(self,root):
        for checkpoint in root.glob('*/checkpoint.json'):
            state=json.loads(checkpoint.read_text(encoding='utf-8'))
            self.ingest(checkpoint.parent.name,state.get('findings',[]),state.get('sources',{}))
