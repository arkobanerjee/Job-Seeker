import unittest
from job_seeker.momentum import summarize

class MomentumTests(unittest.TestCase):
    def test_dates_and_sampling_are_explicit(self):
        rows=[{'observed_at':'2026-10-20T10:00:00Z','returned_count':30,'reported_total':40},{'observed_at':'2026-10-21T10:00:00Z','returned_count':30,'reported_total':45}]
        result=summarize(rows);self.assertEqual(result['delta'],5);self.assertEqual(result['metric'],'reported_total')
        rows[1]['reported_total']=None;result=summarize(rows);self.assertEqual(result['delta'],0);self.assertIn('sample',result['scope'])
    def test_same_day_and_missing_data_do_not_establish_trend(self):
        rows=[{'observed_at':'2026-10-20T10:00:00Z','returned_count':30},{'observed_at':'2026-10-20T11:00:00Z','returned_count':40}]
        self.assertEqual(summarize(rows)['status'],'insufficient_history');self.assertEqual(summarize([])['status'],'insufficient_history')
