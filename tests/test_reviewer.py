import unittest
from job_seeker.reviewer import Review,apply_review

class ReviewTests(unittest.TestCase):
    def test_rejection_requires_recorded_quote(self):
        finding={'kind':'vacancy','fit':'possible'};page={'text':'German C1 is mandatory for this position.'}
        result=apply_review(finding,Review(verdict='reject',reason='German required',blocker_quotes=['German C1 is mandatory for this position.']),page)
        self.assertEqual(result['kind'],'excluded');self.assertEqual(result['fit'],'conflict')
        result=apply_review(finding,Review(verdict='reject',reason='Invented blocker',blocker_quotes=['The applicant must be a citizen of Mars.']),page)
        self.assertEqual(result['kind'],'vacancy');self.assertEqual(result['review_status'],'needs_review')
    def test_accept_never_upgrades_a_rejected_finding(self):
        result=apply_review({'kind':'excluded','fit':'conflict'},Review(verdict='accept',reason='Skills match'),{'text':''})
        self.assertEqual(result['kind'],'excluded')
