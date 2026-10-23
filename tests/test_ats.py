import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from job_seeker.ats import endpoint,parse
from job_seeker.sources import SourceTools
from job_seeker.budget import Ledger

class ATSTests(unittest.TestCase):
    def test_endpoint_scope_and_regions(self):
        self.assertEqual(endpoint('https://jobs.eu.lever.co/acme/abc')[3],'https://api.eu.lever.co/v0/postings/acme/abc?mode=json')
        self.assertIsNone(endpoint('https://jobs.lever.co.evil.example/acme'))
        self.assertIsNone(endpoint('https://boards.greenhouse.io/acme/jobs/not-an-id'))
        self.assertIsNone(endpoint('https://jobs.lever.co/acme/one/extra'))
    def test_greenhouse_posting_and_mismatched_id(self):
        info=endpoint('https://job-boards.greenhouse.io/acme/jobs/12')
        record=parse(info,json.dumps({'id':12,'title':'AI Engineer','location':{'name':'Berlin'},'content':'&lt;p&gt;Build RAG systems&lt;/p&gt;'}))
        self.assertIn('Build RAG systems',record['text']);self.assertNotIn('<p>',record['text'])
        self.assertEqual(record['ats_job_id'],'12')
        with self.assertRaises(ValueError):parse(info,json.dumps({'id':13}))
    def test_lever_lists_are_bounded_and_cannot_cross_tenants(self):
        info=endpoint('https://jobs.lever.co/acme')
        rows=[{'text':'AI Engineer','hostedUrl':'https://jobs.lever.co/acme/'+str(i)} for i in range(40)]
        rows.append({'text':'Wrong tenant','hostedUrl':'https://jobs.lever.co/other/one'})
        record=parse(info,json.dumps(rows))
        self.assertTrue(record['structured_index']);self.assertEqual(len(record['links']),30)
        self.assertFalse(any('/other/' in link for link in record['links']))
    def test_lever_description_and_list_sections(self):
        record=parse(endpoint('https://jobs.lever.co/acme/abc'),json.dumps({'id':'abc','text':'Data Scientist','categories':{'location':'Remote'},'descriptionPlain':'Python models','lists':[{'text':'Requirements','content':'<li>SQL</li>'}]}))
        self.assertIn('Python models',record['text']);self.assertIn('SQL',record['text'])
    def test_source_adapter_retains_original_url_and_api_provenance(self):
        url='https://job-boards.greenhouse.io/acme/jobs/12';info=endpoint(url)
        with tempfile.TemporaryDirectory() as tmp:
            tools=SourceTools(Ledger(Path(tmp)/'b.sqlite3','one'),lambda:None);tools.allowed.add(url)
            with patch('job_seeker.sources.public_get',side_effect=[('https://boards-api.greenhouse.io/robots.txt',404,''),(info[3],200,json.dumps({'id':12,'title':'AI Engineer','content':'RAG'}))]):record=tools.fetch(url)
            self.assertEqual(record['url'],url);self.assertEqual(record['api_url'],info[3]);self.assertEqual(record['http_status'],200)
            self.assertEqual(tools.fetches,1)
    def test_ats_policy_denial_does_not_fall_back(self):
        url='https://jobs.lever.co/acme/abc'
        with tempfile.TemporaryDirectory() as tmp:
            tools=SourceTools(Ledger(Path(tmp)/'b.sqlite3','one'),lambda:None);tools.allowed.add(url)
            with patch('job_seeker.sources.public_get',return_value=('https://api.lever.co/robots.txt',200,'User-agent: *\nDisallow: /')) as get:
                self.assertIn('error',tools.fetch(url));self.assertEqual(get.call_count,1)

    def test_board_counts_keep_total_separate_from_link_sample(self):
        info=endpoint('https://job-boards.greenhouse.io/acme')
        data={'jobs':[{'title':'AI Engineer','absolute_url':'https://job-boards.greenhouse.io/acme/jobs/'+str(i)} for i in range(40)],'meta':{'total':40}}
        record=parse(info,json.dumps(data));self.assertEqual(record['reported_total'],40);self.assertEqual(record['returned_count'],40);self.assertEqual(len(record['links']),30)
