import json
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from job_seeker.context import compact_page,application_form,title_only
from job_seeker.runner import invoke_model,AssessmentTruncated
from job_seeker.settings import load_settings
from job_seeker.budget import Ledger
from job_seeker.research import Report,validate_findings
from test_prototype import finding


class ContextTests(unittest.TestCase):
    def test_title_only_and_application_form_are_distinguished_from_job_details(self):
        self.assertTrue(title_only({'text':'AI Engineer @ Example'},'AI Engineer','Example'))
        self.assertFalse(title_only({'text':'AI Engineer: build RAG services in Python.'},'AI Engineer','Example'))
        self.assertTrue(application_form({'url':'https://example.com/job/123/apply?language=en'}))
        self.assertFalse(application_form({'url':'https://example.com/job/123?apply=true'}))
        title='Senior AI Engineer (w/m/d) @ Example'
        proposal=finding(title=title,evidence_quote=title,source_id='known')
        page={'url':proposal.url,'source_id':'known','http_status':200,'text':title,'observed_at':'today'}
        good,bad=validate_findings(Report(findings=[proposal],limitations=[]),{proposal.url:page})
        self.assertEqual(good,[])
        self.assertIn('Only a title',bad[0]['reason'])
    def test_truncated_provider_reply_retains_charge_and_records_available_usage(self):
        from openai import LengthFinishReasonError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings,_=load_settings();settings.adaptive.enabled=False
            ledger=Ledger(root/'budget.sqlite3','test',.1)
            state={'folder':str(root),'model_calls':0,'usage':[]}
            structured=MagicMock();structured.invoke.side_effect=LengthFinishReasonError(completion=SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10,completion_tokens=50)))
            model=MagicMock();model.with_structured_output.return_value=structured
            with patch('langchain_openai.ChatOpenAI',return_value=model):
                with self.assertRaises(AssessmentTruncated):invoke_model(settings,'Small prompt',ledger,state)
            self.assertEqual(state['model_calls'],1)
            self.assertNotIn('pending_call',state)
            self.assertEqual(ledger.summary()['unreconciled_calls'],0)
            self.assertGreater(ledger.summary()['reserved_usd'],0)
            self.assertEqual(state['research_trace'][-1]['outcome'],'output_limit')

    def test_link_heavy_multilingual_page_stays_bounded(self):
        page={'url':'https://example.com','source_id':'test','text':'漢字'*10000,
              'links':['https://example.com/'+str(i)+'x'*1000 for i in range(500)]}
        small=compact_page(page)
        self.assertLess(len(json.dumps(small,ensure_ascii=False).encode()),19000)
        self.assertGreater(small['context_omissions']['text_bytes'],0)
        self.assertGreater(small['context_omissions']['links'],0)
        self.assertTrue(all(url in page['links'] for url in small['links']))
        self.assertEqual(len(page['text']),20000)

    def test_oversized_link_does_not_hide_later_career_url(self):
        good='https://example.com/careers'
        small=compact_page({'text':'Short text','links':['https://example.com/'+'x'*5000,good]})
        self.assertEqual(small['links'],[good])
        self.assertEqual(small['context_omissions']['text_bytes'],0)
