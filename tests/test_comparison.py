import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from experiments import comparison as c
from job_seeker.budget import Ledger, BudgetExceeded


class ComparisonTests(unittest.TestCase):
    def test_atomic_coverage_has_one_owner(self):
        coverage=c.Coverage()
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims=list(pool.map(lambda i:coverage.claim('https://example.com/jobs/1',str(i)),range(8)))
        self.assertEqual(sum(claimed for claimed,owner in claims),1)
        self.assertEqual(len({owner for claimed,owner in claims}),1)

    def test_observed_vacancy_links_rank_above_navigation(self):
        self.assertGreater(c.link_priority('https://jobs.lever.co/acme/123'),
                           c.link_priority('https://example.com/privacy'))

    def test_coordinated_arm_skips_shared_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary)
            corpus=json.loads((Path(c.__file__).parent/'fixtures/corpus.json').read_text())
            result=c.run_arm(home,'batch','C',corpus['tasks'],lambda ledger,folder:c.FrozenTools(corpus))
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['process_counts']['coverage_skip'],1)
            self.assertEqual(result['process_counts']['fetch_start'],3)
            self.assertEqual(len(result['findings']),2)

    def test_live_assessment_bounds_metadata_but_preserves_source(self):
        backend=object.__new__(c.LiveTools);backend.prompt='Candidate'
        page={'url':'https://example.com','source_id':'test','http_status':200,
              'text':'A job posting','links':['https://example.com/'+str(i) for i in range(100)],
              'unbounded_metadata':'x'*100000}
        with patch.object(backend,'_invoke',return_value=c.Assessment()) as invoke:
            backend.assess(page,'ai')
        prompt=invoke.call_args.args[0]
        self.assertLess(len(prompt),5000)
        self.assertEqual(len(page['links']),100)
        self.assertNotIn('unbounded_metadata',prompt)

    def test_offline_pair_is_isolated_and_records_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary)/'comparison';home.mkdir()
            for name in ('experiment.json','master.md','profile.md','resume.md'):
                source=c.HOME/name
                (home/name).write_bytes(source.read_bytes() if source.exists() else b'')
            # Fixture contains no actual candidate data for the test.
            (home/'profile.md').write_text('Test candidate in Germany',encoding='utf-8')
            (home/'resume.md').write_text('Python and RAG experience',encoding='utf-8')
            (home/'master.md').write_text('{{profile}}\n{{resume}}',encoding='utf-8')
            (home/'experiment.json').write_text(json.dumps({'total_budget_usd':5,
                'production_state_access':False,'production_budget_access':False,
                'model_provider':'openai','model':'gpt-5.6-luna'}))
            with patch.object(c,'HOME',home), patch('socket.socket',side_effect=AssertionError('Network forbidden')), \
                 patch('job_seeker.cloud.Cloud.request',side_effect=AssertionError('Production forbidden')), \
                 patch.object(c,'Ledger',side_effect=AssertionError('Offline budget must remain untouched')):
                folder=c.execute(home)
            results=json.loads((folder/'comparison.json').read_text())
            self.assertEqual({r['arm'] for r in results},{'A','B'})
            self.assertTrue(all(len(r['findings'])==2 for r in results))
            self.assertEqual({f['url'] for f in results[0]['findings']},
                             {f['url'] for f in results[1]['findings']})
            self.assertFalse((home/'budget.sqlite3').exists())
            for trace in folder.glob('*/trace.jsonl'):
                events=[json.loads(line) for line in trace.read_text().splitlines()]
                self.assertTrue(any(e['event_type']=='source_unavailable' for e in events))
                self.assertTrue(any(e['event_type']=='deduplicated' for e in events))
                starts={e['event_id'] for e in events if e['event_type'].endswith('_start')}
                self.assertTrue(all(e['parent_event_id'] in starts for e in events if e.get('parent_event_id')))

    def test_simultaneous_reservations_share_one_run_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'budget.sqlite3'
            Ledger(path,'pair',.30)
            def reserve(_):
                try:Ledger(path,'pair',.30).reserve('test',.10);return True
                except BudgetExceeded:return False
            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(reserve,range(8))),3)
            self.assertEqual(Ledger(path,'pair',.30).summary()['reserved_usd'],.30)

    def test_new_run_is_not_blocked_by_cumulative_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'budget.sqlite3'
            for index in range(5):Ledger(path,str(index),1).reserve('test',1)
            Ledger(path,'new',1).reserve('test',.01)
            self.assertEqual(Ledger(path,'new',1).summary()['total_reserved_usd'],5.01)

    def test_production_workspace_rejected(self):
        with self.assertRaises(ValueError):c.safe_home(c.ROOT/'runs')

    def test_live_direct_call_rejected_before_network(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(ValueError):c.execute(live=True)

    def test_failed_task_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            trace=c.Trace(folder,{'arm':'A'})
            class Broken:
                def search(self,query):raise RuntimeError('do not log credentials')
            result=c.task_run({'id':'test','query':'AI','track':'ai'},'worker',Broken(),trace)
            self.assertEqual(result['status'],'failed')
            events=(folder/'trace.jsonl').read_text()
            self.assertNotIn('do not log credentials',events)
            self.assertIn('search_failure',events)

if __name__=='__main__':unittest.main()
