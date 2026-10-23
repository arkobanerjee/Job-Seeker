"""Durable local question records; answers are task inputs, never permissions."""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime,timezone

class Questions:
    def __init__(self,path):
        path.parent.mkdir(parents=True,exist_ok=True)
        self.path=path
        with closing(sqlite3.connect(path)) as db,db:
            db.execute("CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY, run_id TEXT, revision TEXT, prompt TEXT, reason TEXT, answer TEXT, delivered INTEGER DEFAULT 0)")
            if 'message_id' not in [r[1] for r in db.execute("PRAGMA table_info(questions)")]:
                db.execute("ALTER TABLE questions ADD COLUMN message_id INTEGER")
            if 'cancelled' not in [r[1] for r in db.execute("PRAGMA table_info(questions)")]:db.execute("ALTER TABLE questions ADD COLUMN cancelled INTEGER DEFAULT 0")
    def cancel(self,ident):
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('UPDATE questions SET cancelled=1 WHERE id=?',(ident,))
    def ask(self,run_id,revision,prompt,reason):
        if not prompt.strip() or len(prompt)>1500 or len(reason)>1000: raise ValueError("Invalid question")
        ident=hashlib.sha256(json.dumps([run_id,revision,prompt],ensure_ascii=False).encode()).hexdigest()[:24]
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("INSERT OR IGNORE INTO questions(id,run_id,revision,prompt,reason) VALUES(?,?,?,?,?)",(ident,run_id,revision,prompt,reason))
        return self.get(ident)
    def get(self,ident):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            row=db.execute("SELECT * FROM questions WHERE id=?",(ident,)).fetchone()
            if row is None: raise ValueError("Unknown question")
            return dict(row)
    def answer(self,ident,revision,text):
        if not isinstance(text,str) or not text.strip() or len(text)>4000: raise ValueError("Invalid answer")
        with closing(sqlite3.connect(self.path)) as db,db:
            row=db.execute("SELECT revision,answer FROM questions WHERE id=?",(ident,)).fetchone()
            if row is None or row[0]!=revision: raise ValueError("Unknown or stale question")
            if row[1] is not None:
                if row[1]!=text: raise ValueError("Question already answered")
                return False
            db.execute("UPDATE questions SET answer=? WHERE id=? AND answer IS NULL",(text,ident))
            return True
    def by_message(self,message_id):
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute("SELECT id FROM questions WHERE message_id=?",(message_id,)).fetchone()
            if row is None: raise ValueError("Unknown question message")
            return self.get(row[0])
    def pending(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            return [dict(x) for x in db.execute("SELECT * FROM questions WHERE answer IS NULL AND cancelled=0")]
    def delivered(self,ident,message_id):
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("UPDATE questions SET delivered=1,message_id=? WHERE id=?",(message_id,ident))

def send_question(store,question,on_checkpoint=None):
    from .telegram import send
    if question["delivered"]: return
    from .outbox import Outbox
    outbox=Outbox(store.path.with_name("outbox.sqlite3"))
    outbox.enqueue("question:"+question["id"],"Job Seeker needs input\n"+question["prompt"]+"\nWhy: "+question["reason"]+
         "\nReply directly to this message with your answer.",force_reply=True)
    message_id=outbox.deliver("question:"+question["id"],before_send=on_checkpoint)
    store.delivered(question["id"],message_id)

def accept_reply(store,message,owner_chat):
    import re
    if message.get("chat",{}).get("type")!="private" or str(message.get("chat",{}).get("id"))!=str(owner_chat) or str(message.get("from",{}).get("id"))!=str(owner_chat):
        raise ValueError("Unauthorized reply")
    match=re.fullmatch(r"/answer ([a-f0-9]{24}) ([\s\S]+)",message.get("text",""))
    if not match and message.get("reply_to_message",{}).get("from",{}).get("is_bot"):
        question=store.by_message(message["reply_to_message"].get("message_id"))
        store.answer(question["id"],question["revision"],message.get("text",""))
        return question["run_id"]
    if not match: raise ValueError("Reply must identify a question")
    question=store.get(match[1]); store.answer(question["id"],question["revision"],match[2])
    return question["run_id"]
