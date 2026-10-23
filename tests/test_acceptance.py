import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from job_seeker.acceptance import quality
from job_seeker.runner import Assessment


class AcceptanceTests(unittest.TestCase):
    def test_invalid_evaluation_is_rejected_before_reserving(self):
        class Cloud:
            def request(self,path,*args,**kwargs):
                if path=='settings':return {'config.toml':'[search]\nqueries=[{track="ai",query="synthetic"}]'}
                raise AssertionError('Invalid evaluation must not reserve funds')
        with patch('job_seeker.acceptance.Cloud',Cloud):
            with self.assertRaises(ValueError):quality(envelope=.0001)
            with self.assertRaises(ValueError):quality(review_ids=['not-in-case-set'])

    def test_envelope_precedes_calls_and_labels_stay_out_of_context(self):
        cases=(Path(__file__).parent/'fixtures/quality_cases.json').read_text()
        files={'config.toml':'[search]\nqueries=[{track="ai",query="synthetic"}]',
               'prompts/master.md':'PROFILE {{profile}} RESUME {{resume}}','private/profile.md':'Synthetic candidate'}
        events=[]
        class Cloud:
            def request(self,path,method='GET',body=None,**kwargs):
                events.append(path)
                if path=='settings':return files
                if path=='reserve':
                    if body['amount']!=.4:raise AssertionError('Unexpected acceptance envelope')
                    return {'reserved':True}
                raise AssertionError('Unexpected cloud operation')
        def model(settings,prompt,ledger,state,**kwargs):
            self.assertIn('reserve',events);self.assertNotIn('"expected"',prompt)
            self.assertEqual(settings.limits.run_usd,.4);self.assertEqual(settings.limits.max_model_calls,18)
            events.append('model');return Assessment()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'tests/fixtures';folder.mkdir(parents=True);(folder/'quality_cases.json').write_text(cases)
            with patch('job_seeker.acceptance.ROOT',root),patch('job_seeker.acceptance.Cloud',Cloud),patch('job_seeker.acceptance.invoke_model',side_effect=model):
                output,report=quality()
            self.assertEqual(events[:2],['settings','reserve']);self.assertEqual(events.count('model'),14)
            self.assertEqual(report['cases'],14);self.assertTrue((output/'report.json').exists())
