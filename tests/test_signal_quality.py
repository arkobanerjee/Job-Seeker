import tempfile
import unittest
from pathlib import Path
from job_seeker.signals import Signal,validate_signals
from job_seeker.registry import Registry


class SignalQualityTests(unittest.TestCase):
    def validate(self,quote,event='funding',terms=None,background='Production RAG and data analytics experience'):
        signal=Signal(company='ExampleCorp',title='Company announcement',kind='company',source_id='one',evidence_quote=quote,
                      relevance='Production retrieval matches the candidate RAG experience.',event_type=event,profile_terms=['RAG'] if terms is None else terms)
        page={'source_id':'one','url':'https://example.com/news','http_status':200,'text':quote,'observed_at':'today'}
        return validate_signals([signal],page,'run',background)

    def test_concrete_events_have_distinct_evidence_labels(self):
        for event,verb in [('funding','raised funding'),('expansion','opened a new office'),('hiring','is hiring'),('product','launched a platform'),('deployment','deployed in production')]:
            good,bad=self.validate('ExampleCorp '+verb+' for its production RAG engineering platform.',event)
            self.assertEqual(bad,[])
            self.assertEqual(good[0]['qualification_status'],'qualified')
            self.assertEqual(good[0]['source_ownership'],'unverified')

    def test_generic_biography_and_speculation_are_held_for_investigation(self):
        for quote,event in [('ExampleCorp author writes about RAG and data engineering.','technical_interest'),
                            ('ExampleCorp could secure funding for RAG engineering someday.','funding'),
                            ('ExampleCorp has not raised funding for its RAG engineering platform.','funding')]:
            good,_=self.validate(quote,event)
            self.assertEqual(good[0]['qualification_status'],'investigate')
            self.assertTrue(good[0]['qualification_reasons'])

    def test_wrong_event_and_missing_profile_match_are_not_promoted(self):
        for quote,event,terms in [('ExampleCorp published an article about production RAG.','funding',['RAG']),
                                 ('ExampleCorp raised funding for a furniture company.','funding',['RAG'])]:
            good,_=self.validate(quote,event,terms)
            self.assertEqual(good[0]['qualification_status'],'investigate')
        good,_=self.validate('ExampleCorp raised funding and said it would develop software.',terms=['AI'],background='AI engineering')
        self.assertEqual(good[0]['matched_profile_terms'],[])

    def test_unsupported_quote_is_rejected_and_survives_registry_export(self):
        signal=Signal(company='ExampleCorp',title='Invented announcement',kind='company',source_id='one',evidence_quote='ExampleCorp raised funding for a RAG platform.',relevance='Matches RAG',event_type='funding',profile_terms=['RAG'])
        good,bad=validate_signals([signal],{'source_id':'one','url':'https://example.com/news','http_status':200,'text':'ExampleCorp writes about data.','observed_at':'today'},'run','RAG')
        self.assertEqual(good,[])
        with tempfile.TemporaryDirectory() as tmp:
            registry=Registry(Path(tmp)/'registry.sqlite3');registry.ingest_signals(good,bad)
            saved=registry.export()['rejected_signals'][0]
            self.assertEqual(saved['reason'],'Quote absent from source')
            self.assertEqual(saved['company'],'ExampleCorp')
            self.assertEqual(saved['url'],'https://example.com/news')

    def test_missing_event_fields_do_not_promote_historical_records(self):
        good,_=self.validate('ExampleCorp raised funding for a production RAG platform.',event='unknown',terms=[])
        self.assertEqual(good[0]['qualification_status'],'investigate')
