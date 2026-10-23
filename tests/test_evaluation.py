import json
import unittest
from pathlib import Path
from job_seeker.evaluation import score


CASES=json.loads((Path(__file__).parent/'fixtures/quality_cases.json').read_text())


def prediction(case,**updates):
    finding={'kind':'vacancy','track':'ai','company':'SYNTHETIC Employer',
             'title':case['title'],'url':case['source']['url'],'source_id':case['source']['source_id'],
             'evidence_quote':case['source']['text'],'fit':'possible','fit_reason':'Synthetic test output',
             'language':'unknown','location':'unknown','eligibility':'unknown','concerns':[]}
    finding.update(updates)
    return {'source_type':'employer','findings':[finding]}


class EvaluationTests(unittest.TestCase):
    def test_missing_cases_are_failures_and_count_against_recall(self):
        report=score(CASES,{})
        self.assertEqual(report['submitted'],0);self.assertEqual(report['passed'],0)
        self.assertGreater(report['missed_shortlists'],0);self.assertEqual(report['shortlist_recall'],0)
        self.assertIsNone(report['shortlist_precision'])

    def test_false_shortlist_and_unsupported_eligibility_are_reported(self):
        cases=[CASES[0],CASES[3]]
        report=score(cases,{c['id']:prediction(c,eligibility='Guaranteed sponsorship') for c in cases})
        self.assertEqual(report['false_shortlists'],1)
        self.assertEqual(report['shortlist_precision'],.5)
        self.assertIn('unsupported_eligibility',report['results'][0]['errors'])

    def test_evidence_validation_is_part_of_scoring(self):
        case=CASES[0]
        report=score([case],{case['id']:prediction(case,evidence_quote='invented evidence not found in the original retrieved source')})
        self.assertEqual(report['missed_shortlists'],1)
        self.assertEqual(report['results'][0]['unverified_outputs'],1)

    def test_duplicate_or_unknown_ids_rejected(self):
        with self.assertRaises(ValueError):score([CASES[0],CASES[0]],{})
        with self.assertRaises(ValueError):score(CASES,{'made-up':{}})
