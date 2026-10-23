import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from job_seeker.retention import candidates,evidence_archive,archive_terminal_runs
from job_seeker.catalog import Catalog
from job_seeker.registry import Registry
from job_seeker.questions import Questions
from job_seeker.outbox import Outbox


def run(root,n,status='completed',date='2026-01-01T00:00:00+00:00'):
    ident=f'{n:032x}';folder=root/'runs'/ident;folder.mkdir(parents=True)
    (folder/'checkpoint.json').write_text(json.dumps({'run_id':ident,'status':status,'started_at':date}))
    (folder/'result.json').write_text(json.dumps({'run_id':ident,'status':status,'findings':[]}))
    return ident


class RetentionTests(unittest.TestCase):
    def test_legacy_questions_schema_is_read_conservatively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ident=run(root,1)
            with closing(sqlite3.connect(root/'runs/questions.sqlite3')) as db,db:
                db.execute('CREATE TABLE questions(id TEXT,run_id TEXT,answer TEXT)')
                db.execute('INSERT INTO questions VALUES(?,?,NULL)',('old-question',ident))
            self.assertEqual(candidates(root,keep=0,days=1),[])

    def test_protects_recent_active_questions_and_uncertain_deliveries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);now=datetime(2026,10,23,tzinfo=timezone.utc)
            eligible=run(root,1);run(root,2,'paused');run(root,3,'partial');run(root,4,date='2026-10-22T00:00:00+00:00')
            q=run(root,5);Questions(root/'runs/questions.sqlite3').ask(q,'rev','Synthetic?','Drill')
            o=run(root,6);Outbox(root/'runs/outbox.sqlite3').enqueue('completion:'+o+':receipt','Drill')
            newest=run(root,7,date='2026-10-23T00:00:00+00:00')
            self.assertEqual(candidates(root,keep=1,now=now),[eligible])
            self.assertEqual(candidates(root,keep=20,now=now),[])

    def test_readback_failure_retains_hot_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ident=run(root,1)
            class Cloud:
                def request(self,path,method='GET',body=None,binary=False):
                    return {'sha256':hashlib.sha256(body).hexdigest()} if method=='PUT' else b'wrong bytes'
            with self.assertRaisesRegex(ValueError,'readback'):archive_terminal_runs(Cloud(),root,keep=0,days=1)
            self.assertTrue((root/'runs'/ident/'checkpoint.json').exists())

    def test_deterministic_archive_and_preserved_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ident=run(root,1);catalog=Catalog(root/'runs/catalog.sqlite3')
            catalog.ingest(ident,[{'title':'Data Analyst','company':'Synthetic','url':'https://synthetic.example/role'}])
            job=catalog.list()[0]['id'];catalog.decide(job,'apply_anyway','Owner decision')
            first=evidence_archive(root,ident);self.assertEqual(first,evidence_archive(root,ident))
            class Cloud:
                data=None
                def request(self,path,method='GET',body=None,binary=False):
                    if method=='PUT':self.data=body;return {'sha256':hashlib.sha256(body).hexdigest()}
                    return self.data
            ids,_=archive_terminal_runs(Cloud(),root,keep=0,days=1)
            self.assertEqual(ids,[ident]);self.assertFalse((root/'runs'/ident/'checkpoint.json').exists())
            self.assertEqual(catalog.list()[0]['decision'],'apply_anyway')
            self.assertTrue((root/'runs/catalog.sqlite3').exists());self.assertTrue((root/'runs/registry.sqlite3').exists())
