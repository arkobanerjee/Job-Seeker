import unittest
from job_seeker.research import Report,validate_findings
from job_seeker.evaluation import score
from test_prototype import finding,URL,QUOTE


class ContractTests(unittest.TestCase):
    def test_explicit_unknowns_normalize_without_losing_explanation(self):
        item=finding(eligibility='Unknown; employer policy not supplied',eligibility_status='unknown',language='English required',language_status='stated')
        good,_=validate_findings(Report(findings=[item],limitations=[]),{URL:{'http_status':200,'text':QUOTE,'observed_at':'today'}})
        self.assertEqual(good[0]['eligibility'],'unknown')
        self.assertEqual(good[0]['eligibility_details'],'Unknown; employer policy not supplied')
        self.assertEqual(good[0]['language'],'English required')

    def test_legacy_claims_are_not_silently_reclassified_as_unknown(self):
        good,_=validate_findings(Report(findings=[finding(eligibility='Sponsorship available')],limitations=[]),{URL:{'http_status':200,'text':QUOTE,'observed_at':'today'}})
        self.assertEqual(good[0]['eligibility'],'Sponsorship available')
        self.assertIsNone(good[0]['eligibility_status'])

    def test_closed_evidence_stays_excluded_with_reason_and_ats_title(self):
        good,_=validate_findings(Report(findings=[finding()],limitations=[]),{URL:{'http_status':200,'text':QUOTE,'observed_at':'today','closed_marker':True,'posting_title':'Applied AI Engineer'}})
        self.assertEqual(good[0]['kind'],'excluded');self.assertEqual(good[0]['listing_status'],'closed')
        self.assertIn('closed',good[0]['rejection_reasons'][0]);self.assertIn('reference',good[0]['availability'])

    def test_signal_only_outcome_requires_valid_source_evidence(self):
        text='SYNTHETIC Employer announced a new analytics product without advertising any particular role.'
        case={'id':'signal','title':'Announcement','source':{'url':URL,'source_id':'signal','http_status':200,'text':text,'observed_at':'today'},'expected':{'kind':'signal'}}
        output={'source_type':'signal','signals':[{'company':'SYNTHETIC Employer','title':'Analytics product announcement','kind':'product','source_id':'signal','evidence_quote':text,'relevance':'Company watch signal'}]}
        self.assertEqual(score([case],{'signal':output})['passed'],1)
        output['signals'][0]['evidence_quote']='Invented source evidence that does not appear in the retrieved text.'
        self.assertEqual(score([case],{'signal':output})['passed'],0)
