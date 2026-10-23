import unittest
from job_seeker.competitors import CompetitorLead,validate_leads,lead_query
from job_seeker.settings import Settings
from job_seeker.signals import query_plan

class CompetitorTests(unittest.TestCase):
    def test_both_names_quote_and_known_seed_required(self):
        text='Example Company and Rival Company are alternative platforms for RAG.'
        lead=CompetitorLead(seed_company='Example Company',company='Rival Company',evidence_quote=text,source_id='known')
        page={'url':'https://example.org/comparison','text':text,'source_id':'known','http_status':200}
        self.assertEqual(len(validate_leads([lead],page,['Example Company'],'run')),1)
        self.assertFalse(validate_leads([lead],page,[],'run'))
        lead.source_id='invented';self.assertFalse(validate_leads([lead],page,['Example Company'],'run'))
    def test_query_operators_are_not_taken_from_company_names(self):
        query=lead_query('Company" site:linkedin.com OR x')
        self.assertNotIn('site:',query);self.assertTrue(query.endswith('careers'))
    def test_expansion_reserves_existing_search_slot(self):
        settings=Settings(search={'queries':[{'track':'ai','query':'AI jobs'}]*6})
        self.assertEqual(len(query_plan(settings,reserved=1)[0]),5)
