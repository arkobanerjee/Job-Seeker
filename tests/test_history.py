import json
import tempfile
import unittest
from pathlib import Path
from job_seeker.history import run_history
from job_seeker.tracing import trace_summary

class HistoryTests(unittest.TestCase):
    def test_trace_allowlist_preserves_sequence_and_omits_private_inputs(self):
        state={'trace_scope':'new_run_actions','research_trace':[
            {'at':'one','type':'plan','prompt':'SECRET_CV','decision':{'explanation':'Change title after senior results','question':'SECRET_ANSWER','coverage_gaps':['Data roles'],'action':'research'},'admitted':{'queries':[{'query':'junior ML Germany'}],'inspect_urls':['https://example.com/job']}},
            {'at':'two','type':'search_start','query':'junior ML Germany','api_key':'SECRET_KEY'},
            {'at':'three','type':'stop','reason':'time_limit'}]}
        summary=trace_summary(state)
        self.assertEqual([e['sequence'] for e in summary['events']],[1,2,3])
        self.assertEqual(summary['events'][0]['queries'],['junior ML Germany'])
        self.assertNotIn('SECRET',json.dumps(summary))

    def test_trace_truncation_keeps_latest_stop_and_explicit_omission_count(self):
        state={'research_trace':[{'type':'search_end','query':'x'*300} for _ in range(100)]+[{'type':'stop','reason':'page_limit'}]}
        summary=trace_summary(state,max_bytes=600)
        self.assertEqual(summary['events'][-1]['reason'],'page_limit')
        self.assertGreater(summary['omitted_events'],0)
        self.assertEqual(len(summary['events'])+summary['omitted_events'],101)
        self.assertEqual(summary['scope'],'partial_saved_actions')

    def test_history_reports_unread_queue_and_stop_reason_without_inventing_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/('b'*32);folder.mkdir()
            state={'run_id':'b'*32,'status':'partial','stop_reason':'page_limit','queue':[{'url':'one'},{'url':'two'}],'pages_done':['one']}
            (folder/'checkpoint.json').write_text(json.dumps(state))
            row=run_history(root)[0]
            self.assertEqual(row['unread_pages'],1)
            self.assertEqual(row['stop_reason'],'page_limit')
            self.assertEqual(row['trace']['events'],[])

    def test_history_caps_trace_export_across_many_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for n in range(45):
                ident=format(n,'032x');folder=root/ident;folder.mkdir()
                state={'run_id':ident,'status':'completed','research_trace':[{'type':'search_end','query':'x'*300} for _ in range(60)]}
                (folder/'checkpoint.json').write_text(json.dumps(state))
            rows=run_history(root)
            self.assertLess(sum(len(json.dumps(r['trace'],ensure_ascii=False).encode()) for r in rows),650000)
            self.assertTrue(any(r['trace']['omitted_events'] for r in rows))

    def test_summary_omits_sensitive_inputs_and_reports_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/('a'*32);folder.mkdir()
            state={'run_id':'a'*32,'status':'partial','cloud_envelope':True,'started_at':'2026-10-23','config':{'monitoring':{'enabled':True}},'prompt':'private profile','sources':{'url':{'text':'raw private input'}},'limitations':['Page unavailable'],'model_calls':1}
            (folder/'checkpoint.json').write_text(json.dumps(state))
            rows=run_history(root);self.assertTrue(rows[0]['can_resume']);self.assertEqual(rows[0]['mode'],'monitor')
            self.assertNotIn('private',json.dumps(rows));self.assertNotIn('sources',rows[0]);self.assertIsNone(rows[0]['observed_estimate_usd'])
            state['cloud_envelope']=False;(folder/'checkpoint.json').write_text(json.dumps(state))
            self.assertFalse(run_history(root)[0]['can_resume'])
