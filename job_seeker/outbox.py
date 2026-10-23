"""Durable delivery receipts. Uncertain sends are never retried automatically."""
import json
import sqlite3
import time
from contextlib import closing

class Outbox:
    def __init__(self,path):
        path.parent.mkdir(parents=True,exist_ok=True);self.path=path
        with closing(sqlite3.connect(path)) as db,db:
            db.execute("CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,payload TEXT,status TEXT,attempts INTEGER DEFAULT 0,retry_at REAL DEFAULT 0,message_id INTEGER)")
    def enqueue(self,ident,text,force_reply=False):
        payload=json.dumps({'text':text,'force_reply':force_reply})
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("INSERT OR IGNORE INTO notifications(id,payload,status) VALUES(?,?,'pending')",(ident,payload))
    def deliver(self,ident,before_send=None):
        from .telegram import send,DeliveryUncertain
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload,status,attempts,retry_at,message_id FROM notifications WHERE id=?',(ident,)).fetchone()
            if not row:raise ValueError('Unknown notification')
            payload,status,attempts,retry_at,message_id=row
            if status=='sent':return message_id
            if status!='pending' or attempts>=5 or retry_at>time.time():raise ValueError('Delivery deferred or uncertain')
            db.execute("UPDATE notifications SET status='sending',attempts=attempts+1 WHERE id=?",(ident,))
        try:
            if before_send:before_send()
            message_id=send(**json.loads(payload))
        except DeliveryUncertain:
            with closing(sqlite3.connect(self.path)) as db,db:db.execute("UPDATE notifications SET status='uncertain' WHERE id=?",(ident,))
            raise
        except ValueError:
            with closing(sqlite3.connect(self.path)) as db,db:db.execute("UPDATE notifications SET status=?,retry_at=? WHERE id=?",("failed" if attempts+1>=5 else "pending",time.time()+min(3600,30*2**attempts),ident))
            raise
        with closing(sqlite3.connect(self.path)) as db,db:db.execute("UPDATE notifications SET status='sent',message_id=? WHERE id=?",(message_id,ident))
        return message_id
    def drain(self,before_send=None):
        with closing(sqlite3.connect(self.path)) as db:ids=[r[0] for r in db.execute("SELECT id FROM notifications WHERE status='pending' AND attempts<5 AND retry_at<=? LIMIT 20",(time.time(),))]
        for ident in ids:
            try:self.deliver(ident,before_send)
            except ValueError:pass
    def summary(self):
        with closing(sqlite3.connect(self.path)) as db:
            return [{'id':i,'status':'uncertain' if s=='sending' else s,'attempts':a,'retry_at':r} for i,s,a,r in db.execute('SELECT id,status,attempts,retry_at FROM notifications')]
