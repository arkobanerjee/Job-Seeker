import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from job_seeker.boards import board_targets,observe
from job_seeker.registry import Registry
from job_seeker.settings import Monitoring


class BoardTests(unittest.TestCase):
    def test_targets_deduplicate_tenants_and_are_bounded(self):
        class Registry:
            def export(self):return {'sources':[{'url':'https://boards.greenhouse.io/acme/jobs/12'},{'url':'https://job-boards.greenhouse.io/acme'},{'url':'https://jobs.eu.lever.co/example/id'},{'url':'https://private.example/other'}]}
        self.assertEqual(board_targets(Registry(),[],2),['https://job-boards.greenhouse.io/acme','https://jobs.eu.lever.co/example'])
        with self.assertRaises(ValueError):Monitoring(board_urls=['https://jobs.lever.co/acme/id'])

    def test_first_real_observation_is_not_a_trend_and_uses_no_paid_tools(self):
        url='https://job-boards.greenhouse.io/acme'
        with tempfile.TemporaryDirectory() as tmp:
            registry=Registry(Path(tmp)/'registry.sqlite3')
            responses=[('https://boards-api.greenhouse.io/robots.txt',404,''),('https://boards-api.greenhouse.io/v1/boards/acme/jobs',200,json.dumps({'jobs':[],'meta':{'total':0}}))]
            with patch('job_seeker.sources.public_get',side_effect=responses),patch('job_seeker.sources.SourceTools.search',side_effect=AssertionError('Paid search forbidden')):
                result=observe(registry,'a'*32,[url],1)
            self.assertTrue(result['targets'][0]['count_observed']);self.assertEqual(result['model_calls'],0)
            self.assertEqual(registry.momentum()[0]['status'],'insufficient_history')

    def test_unavailable_is_not_a_zero_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry=Registry(Path(tmp)/'registry.sqlite3')
            with patch('job_seeker.sources.public_get',return_value=('https://boards-api.greenhouse.io/robots.txt',403,'')):
                result=observe(registry,'b'*32,['https://job-boards.greenhouse.io/acme'],1)
            self.assertFalse(result['targets'][0]['count_observed']);self.assertEqual(registry.momentum(),[])

    def test_disabled_observer_never_touches_state_or_budget(self):
        from job_seeker.cloud import observe_cloud_boards
        calls=[]
        class Cloud:
            def request(self,path,*args,**kwargs):
                calls.append(path)
                if path!='settings':raise AssertionError('Unexpected state or budget operation')
                return {'config.toml':'[search]\nqueries=[{track="ai",query="example"}]\n[monitoring]\nboard_observations=false'}
        with patch('job_seeker.cloud.Cloud',Cloud),patch.dict('os.environ',{'GITHUB_ACTIONS':'true'}):
            self.assertEqual(observe_cloud_boards()['reason'],'board_observations_disabled')
        self.assertEqual(calls,['settings'])

    def test_serialized_observer_persists_counts_with_version_check_without_reserving(self):
        from job_seeker.cloud import observe_cloud_boards,pack
        from job_seeker.budget import Ledger
        calls=[];writes=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Ledger(root/'runs/budget.sqlite3','seed')
            initial=pack(root)
            class Cloud:
                def request(self,path,method='GET',body=None,*args,**kwargs):
                    calls.append(path)
                    if path=='settings':return {'config.toml':'[search]\nqueries=[{track="ai",query="example"}]\n[monitoring]\nboard_urls=["https://job-boards.greenhouse.io/acme"]'}
                    if path=='state' and method=='GET':return initial,'"initial-version"'
                    if path=='state' and method=='PUT':
                        writes.append(kwargs);return {'saved':True}
                    raise AssertionError('Unexpected operation '+path)
                def sync_views(self,root):pass
            responses=[('https://boards-api.greenhouse.io/robots.txt',404,''),('https://boards-api.greenhouse.io/v1/boards/acme/jobs',200,json.dumps({'jobs':[],'meta':{'total':0}}))]
            with patch('job_seeker.cloud.Cloud',Cloud),patch('job_seeker.cloud.backup_cloud'),patch('job_seeker.sources.public_get',side_effect=responses),patch.dict('os.environ',{'GITHUB_ACTIONS':'true'}):
                result=observe_cloud_boards()
            self.assertEqual(result['model_calls'],0);self.assertTrue(result['targets'][0]['count_observed'])
            self.assertEqual(writes,[{'expected_etag':'"initial-version"'}]);self.assertNotIn('reserve',calls)
