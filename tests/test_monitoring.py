import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from job_seeker.monitoring import change_kind,scheduled_cap
from job_seeker.settings import Settings
from job_seeker.catalog import Catalog

class MonitoringPolicyTests(unittest.TestCase):
    def test_budget_never_expands_and_gate_stops_daily_checks(self):
        settings=Settings(search={'queries':[{'track':'ai','query':'AI roles'}]})
        self.assertEqual(scheduled_cap(settings,{'ceiling':5,'reserved':4.75}),0.25)
        self.assertIsNone(scheduled_cap(settings,{'ceiling':5,'reserved':4.76}))
        settings.limits.run_usd=0.1
        self.assertEqual(scheduled_cap(settings,{'ceiling':5,'reserved':4.8}),0.1)
    def test_material_changes_ignore_collection_metadata(self):
        item={'title':'AI Engineer','fit':'possible','location':'Berlin'}
        self.assertEqual(change_kind(None,item),'new')
        self.assertEqual(change_kind(item,{**item,'observed_at':'tomorrow','assessment_reused':True}),'unchanged')
        self.assertEqual(change_kind(item,{**item,'location':'Munich'}),'changed')
    def test_catalog_detects_novelty_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Catalog(Path(tmp)/'catalog.sqlite3');item={'company':'Example','title':'AI Engineer','url':'https://example.org/job','fit':'possible'}
            store.ingest('one',[item]);self.assertEqual(item['opportunity_change'],'new')
            store.ingest('two',[item]);self.assertEqual(item['opportunity_change'],'unchanged')
            item['fit']='conflict';store.ingest('three',[item]);self.assertEqual(item['opportunity_change'],'changed')
    def test_disabled_schedule_does_not_reserve_or_run(self):
        from job_seeker.cloud import run_cloud
        settings=Settings(search={'queries':[{'track':'ai','query':'AI roles'}]});calls=[]
        class FakeCloud:
            def request(self,path,method='GET',body=None,**kwargs):
                calls.append(path)
                if path=='state':return b'','"test"'
                if path=='settings':return {}
                if path=='monitor-status':return {'saved':True}
                raise AssertionError('Unexpected API call '+path)
        with tempfile.TemporaryDirectory() as tmp,patch('job_seeker.cloud.ROOT',Path(tmp)),patch('job_seeker.cloud.Cloud',FakeCloud),patch('job_seeker.cloud.unpack'),patch('job_seeker.cloud.load_settings',return_value=(settings,Path(tmp))),patch.dict('os.environ',{'GITHUB_ACTIONS':'true'}):
            folder,result=run_cloud(monitor=True,scheduled=True)
            self.assertIsNone(folder);self.assertEqual(result['reason'],'schedule_disabled');self.assertNotIn('reserve',calls)
