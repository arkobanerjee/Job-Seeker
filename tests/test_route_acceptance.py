import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from job_seeker.route_acceptance import evaluate
from job_seeker.runner import Assessment
from job_seeker.competitors import CompetitorLead
from job_seeker.corroboration import CorroborationReview


class RouteAcceptanceTests(unittest.TestCase):
    def test_two_probes_share_precharged_envelope_and_validate_quotes(self):
        a='Example announced a new engineering platform with a public launch.'
        b='Example has launched a new platform for engineering teams this week.'
        page={'url':'https://example.test/compare','source_id':'comparison','http_status':200,'text':'Example and Other are compared as alternative vector search products.','observed_at':'today'}
        spec={'signals':[{'company':'Example','kind':'product','url':'https://example.test/news','evidence_quote':a},{'company':'Example','kind':'product','url':'https://other.test/news','evidence_quote':b}], 'comparison_page':page,'known_companies':['Example'],'expected_company':'Other','expected_verdict':'supports_same_claim'}
        calls=[]
        class Cloud:
            def request(self,path,method='GET',body=None):
                calls.append(path)
                if path=='settings':return {'config.toml':'[search]\nqueries=[{track="ai",query="example"}]'}
                if path=='reserve':
                    if body['amount']!=.04:raise AssertionError('Unexpected envelope')
                    return {'reserved':True}
                raise AssertionError('Unexpected cloud operation')
        def model(config,prompt,ledger,state,schema=None):
            self.assertIn('reserve',calls);self.assertNotIn('expected_company',prompt)
            if schema:return CorroborationReview(verdict='supports_same_claim',reason='Same claim',quote_a=a,quote_b=b)
            return Assessment(competitors=[CompetitorLead(seed_company='Example',company='Other',source_id='comparison',evidence_quote=page['text'])])
        with tempfile.TemporaryDirectory() as tmp,patch('job_seeker.route_acceptance.ROOT',Path(tmp)),patch('job_seeker.route_acceptance.Cloud',Cloud),patch('job_seeker.route_acceptance.invoke_model',side_effect=model):
            _,report=evaluate(spec)
        self.assertTrue(report['competitor_passed']);self.assertTrue(report['corroboration_passed'])
        self.assertEqual(report['corroboration']['independence'],'publisher_independence_unverified')
        self.assertEqual(calls,['settings','reserve'])
