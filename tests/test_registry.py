import tempfile
import unittest
from pathlib import Path
from job_seeker.registry import Registry,source_info

class RegistryTests(unittest.TestCase):
    def test_shared_ats_keeps_company_identity_separate_and_reimport_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Registry(Path(tmp)/'registry.sqlite3')
            a='https://jobs.lever.co/alpha/job';b='https://jobs.lever.co/beta/job'
            rows=[{'company':'Alpha','url':a},{'company':'Beta','url':b}]
            record={a:{'http_status':200,'text':'AI role','observed_at':'2026-10-23'}}
            store.ingest('one',rows,record);store.ingest('one',rows,record)
            exported=store.export();self.assertEqual(len(exported['companies']),2)
            self.assertEqual(len(exported['sources'][0]['history']),1)
            self.assertEqual(source_info(a)['ats'],'Lever')
            self.assertIsNone(source_info('https://lever.co.evil.example/job')['ats'])
    def test_changed_and_unavailable_are_distinct_from_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Registry(Path(tmp)/'registry.sqlite3');url='https://example.org/jobs'
            for run,text,code,date in [('one','AI',200,'2026-10-20'),('two','AI',200,'2026-10-21'),('three','AI and DS',200,'2026-10-22'),('four','',404,'2026-10-23')]:
                store.ingest(run,[],{url:{'http_status':code,'text':text,'observed_at':date}})
            history=store.export()['sources'][0]['history']
            self.assertEqual([x['change'] for x in history],['first_observation','unchanged','text_changed','unknown'])
            self.assertEqual(history[-1]['status'],'unavailable')
    def test_private_and_unsupported_sources_rejected(self):
        with self.assertRaises(ValueError):source_info('http://example.org/jobs')
        with self.assertRaises(ValueError):source_info('https://linkedin.com/jobs')
