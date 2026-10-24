import unittest
from job_seeker.settings import load_settings
from job_seeker.vacancy import navigation_candidates,navigation_rank,coverage_memory


class VacancyTests(unittest.TestCase):
    def test_only_observed_same_company_or_supported_ats_navigation(self):
        page={'url':'https://employer.example/blog','links':[
            'https://other.example/careers','https://employer.example/privacy',
            'https://employer.example/careers','https://jobs.lever.co/employer',
            'https://jobs.lever.co/employer/abc-123','https://employer.example/careers']}
        self.assertEqual(navigation_candidates(page,2),['https://jobs.lever.co/employer/abc-123','https://jobs.lever.co/employer'])
        self.assertEqual(navigation_candidates(page,0),[])

    def test_coverage_hints_do_not_claim_success_from_failed_query(self):
        settings,_=load_settings()
        state={'attempted_queries':['AI engineer Germany'], 'sources':{'https://example.com/job':{'http_status':410}},
               'vacancy_outcomes':[{'closed_marker':True,'excluded':1}]}
        memory=coverage_memory(settings,state)
        self.assertNotIn('AI engineer',memory['role_terms_not_yet_queried']['ai'])
        self.assertIn('machine learning engineer',memory['role_terms_not_yet_queried']['ai'])
        self.assertNotIn('Germany',memory['regions_not_yet_queried'])
        self.assertEqual(memory['failed_pages'][0]['status'],410)
        self.assertEqual(memory['recent_page_outcomes'][0]['excluded'],1)

    def test_tracking_paths_do_not_override_navigation_rank(self):
        self.assertLess(navigation_rank('https://example.com/jobs/123'),navigation_rank('https://example.com/privacy?next=/jobs/123'))
