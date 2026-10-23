"""Durable, deduplicated findings with independent human decisions and history."""
from contextlib import closing
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

DECISIONS = {"unreviewed", "saved", "apply_anyway", "applied", "dismissed"}

class Catalog:
    def __init__(self,path):
        self.path=path
        path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, payload TEXT NOT NULL, first_seen TEXT, last_seen TEXT,
              decision TEXT NOT NULL DEFAULT 'unreviewed', note TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS observations(
              job_id TEXT, run_id TEXT, payload TEXT, created TEXT,
              PRIMARY KEY(job_id,run_id));
            CREATE TABLE IF NOT EXISTS decisions(
              job_id TEXT, decision TEXT, note TEXT, created TEXT);
            """)

    def ingest(self,run_id,findings):
        now=datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.path)) as db,db:
            for f in findings:
                ident=hashlib.sha256((f["url"]+"\n"+f["title"].casefold()).encode()).hexdigest()[:24]
                data=json.dumps(f,ensure_ascii=False)
                db.execute("INSERT INTO jobs(id,payload,first_seen,last_seen) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,last_seen=excluded.last_seen",(ident,data,now,now))
                db.execute("INSERT OR REPLACE INTO observations VALUES(?,?,?,?)",(ident,run_id,data,now))

    def list(self):
        with closing(sqlite3.connect(self.path)) as db:
            return [{**json.loads(p),"id":i,"first_seen":a,"last_seen":b,"decision":d,"note":n}
                    for i,p,a,b,d,n in db.execute("SELECT id,payload,first_seen,last_seen,decision,note FROM jobs ORDER BY last_seen DESC")]

    def decide(self,ident,decision,note=""):
        if decision not in DECISIONS or len(note)>4000: raise ValueError("Invalid decision or note")
        with closing(sqlite3.connect(self.path)) as db,db:
            cur=db.execute("UPDATE jobs SET decision=?,note=? WHERE id=?",(decision,note,ident))
            if cur.rowcount!=1: raise ValueError("Unknown job")
            db.execute("INSERT INTO decisions VALUES(?,?,?,?)",(ident,decision,note,datetime.now(timezone.utc).isoformat()))

    def import_runs(self,root):
        for folder in sorted(root.iterdir()):
            if not folder.is_dir(): continue
            for name in ("result.json","review.json"):
                file=folder/name
                if file.exists():
                    result=json.loads(file.read_text(encoding="utf-8"))
                    findings=result.get("findings",[])
                    checkpoint=folder/"checkpoint.json"
                    if checkpoint.exists():
                        from .provenance import discovery_trails
                        state=json.loads(checkpoint.read_text(encoding="utf-8"))
                        findings=[{**f,"discovery_trails":f.get("discovery_trails") or discovery_trails(f["url"],state.get("cache",{}),state.get("sources",{}),folder.name)} for f in findings]
                    self.ingest(folder.name,findings)
