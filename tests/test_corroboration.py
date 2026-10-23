import unittest
from job_seeker.corroboration import candidate_pairs,checked_result,CorroborationReview

class CorroborationTests(unittest.TestCase):
    def test_duplicate_quotes_and_same_host_are_not_independent_evidence(self):
        a={'company':'Example','kind':'product','url':'https://a.example/post','evidence_quote':'Example launched a RAG platform for enterprise customers.'}
        b={**a,'url':'https://b.example/post'}
        self.assertEqual(candidate_pairs([a,b]),[])
        b['evidence_quote']='The new Example RAG platform was announced for enterprise use.'
        self.assertEqual(len(candidate_pairs([a,b])),1)
        b['url']='https://a.example/another';self.assertEqual(candidate_pairs([a,b]),[])
    def test_verdict_quotes_and_publisher_ownership_are_checked(self):
        pair=[{'company':'Example','kind':'product','url':'https://a.example/post','evidence_quote':'Example launched a RAG platform for enterprise customers.'},{'company':'Example','kind':'product','url':'https://b.example/post','evidence_quote':'The new Example RAG platform was announced for enterprise use.'}]
        decision=CorroborationReview(verdict='supports_same_claim',reason='Same launch',quote_a=pair[0]['evidence_quote'],quote_b=pair[1]['evidence_quote'])
        self.assertEqual(checked_result('id',pair,decision,{})['independence'],'publisher_independence_unverified')
        self.assertEqual(checked_result('id',pair,decision,{'one':['a.example'],'two':['b.example']})['independence'],'configured_distinct_publishers')
        self.assertEqual(checked_result('id',pair,decision,{'one':['a.example','b.example']})['independence'],'same_configured_publisher')
        decision.quote_b='Invented evidence never present in any supplied excerpt.'
        self.assertEqual(checked_result('id',pair,decision,{})['verdict'],'insufficient')
