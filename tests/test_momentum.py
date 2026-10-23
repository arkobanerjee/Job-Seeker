import unittest
from job_seeker.momentum import summarize

class MomentumTests(unittest.TestCase):
    def test_dates_and_sampling_are_explicit(self):
        rows=[{'observed_at':'2026-10-20T10:00:00Z','returned_count':30,'reported_total':40},{'observed_at':'2026-10-21T10:00:00Z','returned_count':30,'reported_total':45}]
        rows=[dict(r,ats_provider='greenhouse',ats_tenant='example',api_url='https://boards-api.greenhouse.io/v1/boards/example/jobs',collection_scope='same-sample') for r in rows]
        result=summarize(rows);self.assertEqual(result['delta'],5);self.assertEqual(result['metric'],'reported_total')
        rows[1]['reported_total']=None;result=summarize(rows);self.assertEqual(result['delta'],0);self.assertIn('sample',result['scope'])
    def test_same_day_and_missing_data_do_not_establish_trend(self):
        rows=[{'observed_at':'2026-10-20T10:00:00Z','returned_count':30},{'observed_at':'2026-10-20T11:00:00Z','returned_count':40}]
        self.assertEqual(summarize(rows)['status'],'insufficient_history');self.assertEqual(summarize([])['status'],'insufficient_history')

    def test_changed_sample_scope_and_missing_provenance_cannot_show_growth(self):
        base={'ats_provider':'lever','ats_tenant':'example','api_url':'https://api.lever.co/v0/postings/example?limit=100','collection_scope':'bounded','sample_limit':100,'returned_count':50}
        rows=[dict(base,observed_at='2026-10-20T10:00:00Z'),dict(base,observed_at='2026-10-21T10:00:00Z',sample_limit=20,returned_count=20)]
        self.assertEqual(summarize(rows)['status'],'incomparable_history')
        del rows[0]['ats_provider'];self.assertEqual(summarize(rows)['status'],'incomparable_history')

    def test_timezone_ordering_uses_real_instants(self):
        base={'ats_provider':'greenhouse','ats_tenant':'example','reported_total':10}
        rows=[dict(base,observed_at='2026-10-20T23:30:00-03:00'),dict(base,observed_at='2026-10-21T03:00:00Z',reported_total=11)]
        self.assertEqual(summarize(rows)['status'],'insufficient_history')

    def test_two_new_dates_establish_a_new_comparable_baseline(self):
        base={'ats_provider':'lever','ats_tenant':'example','api_url':'https://api.lever.co/v0/postings/example?limit=20','collection_scope':'bounded','sample_limit':20,'returned_count':15}
        rows=[dict(base,observed_at='2026-10-19T10:00:00Z',sample_limit=100,returned_count=50),dict(base,observed_at='2026-10-20T10:00:00Z'),dict(base,observed_at='2026-10-21T10:00:00Z',returned_count=17)]
        result=summarize(rows);self.assertEqual(result['delta'],2);self.assertTrue(result['baseline_reset'])
