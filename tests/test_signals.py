import tempfile
import unittest
from pathlib import Path
from job_seeker.signals import Signal,validate_signals,query_plan
from job_seeker.registry import Registry
from job_seeker.settings import Settings

TEXT='Example Company builds RAG systems for enterprise customers. Launch announced on 2026-10-20.'
PAGE={'url':'https://example.org/blog','http_status':200,'source_id':'known','text':TEXT,'observed_at':'2026-10-23'}
def signal(**kw):return Signal(**({'company':'Example Company','title':'RAG platform launch','kind':'product','source_id':'known','evidence_quote':TEXT,'relevance':'Uses candidate RAG skills','event_date':'2026-10-20'}|kw))

class SignalTests(unittest.TestCase):
    def test_evidence_not_an_inferred_vacancy(self):
        good,bad=validate_signals([signal()],PAGE,'run');self.assertFalse(bad)
        self.assertEqual(good[0]['event_date'],'2026-10-20');self.assertIn('no matching vacancy',good[0]['classification'])
        for item in [signal(source_id='fake'),signal(evidence_quote='Invented quote that is definitely long enough'),signal(company='Other Company')]:
            good,bad=validate_signals([item],PAGE,'run');self.assertFalse(good);self.assertTrue(bad)
    def test_unsubstantiated_event_date_is_unknown(self):
        good,_=validate_signals([signal(event_date='2026-10-23')],PAGE,'run');self.assertIsNone(good[0]['event_date'])
    def test_query_families_share_existing_limit_and_rotate(self):
        settings=Settings(search={'queries':[{'track':'ai','query':'vacancy'}]*6},signals={'enabled':True,'max_queries':2,'queries':[{'track':'ai','route':'technology','query':'technology'},{'track':'data','route':'hiring','query':'hiring'},{'track':'ai','route':'product','query':'product'}]})
        plan,count=query_plan(settings,0);self.assertEqual(len(plan),6);self.assertEqual(count,2)
        self.assertEqual(plan[-1]['route'],'hiring');self.assertEqual(query_plan(settings,2)[0][-2]['route'],'product')
        settings.limits.max_searches=1;self.assertEqual(query_plan(settings)[1],0)
    def test_signals_persist_without_creating_job_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Registry(Path(tmp)/'registry.sqlite3');good,_=validate_signals([signal()],PAGE,'run')
            store.ingest_signals(good);store.ingest_signals(good);exported=store.export()
            self.assertEqual(len(exported['signals']),1);self.assertEqual(len(exported['companies']),1)
            self.assertEqual(store.signal_offset(2),0);self.assertEqual(store.signal_offset(),2)
