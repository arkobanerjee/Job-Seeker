import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_product import setup
from test_prototype import finding
from job_seeker.settings import load_settings
from job_seeker.company_discovery import operation_settings,seed_queries,company_memory,cover_themes
from job_seeker.runner import run,Assessment
from job_seeker.adaptive import ResearchDecision
from job_seeker.signals import Signal
from job_seeker.sources import SourceTools


class CompanyDiscoveryTests(unittest.TestCase):
    def test_company_refinement_cannot_drift_into_vacancy_query(self):
        settings,_=load_settings()
        state={'started_at':'2026-10-24T08:00:00+00:00','searches':5}
        state['attempted_queries']=[s['query'] for s in seed_queries(settings,state['started_at'])]
        decision=ResearchDecision(action='research',explanation='Refine',queries=[{'track':'ai','query':'AI Engineer Germany careers individual vacancy'},{'track':'ai','query':'Germany RAG product launch announcement'}])
        checked=cover_themes(decision,settings,state)
        self.assertEqual([q.query for q in checked.queries],['Germany RAG product launch announcement'])
        self.assertIn('Vacancy-focused query omitted in company mode',checked.coverage_gaps)
    def test_separate_limits_do_not_mutate_vacancy_settings(self):
        settings,_=load_settings()
        company=operation_settings(settings,'company')
        self.assertEqual(settings.limits.max_searches,6)
        self.assertEqual(company.limits.max_searches,10)
        self.assertEqual(company.limits.max_pages,24)
        self.assertEqual(company.limits.run_usd,0.40)
        self.assertEqual(company.model.max_output_tokens,8000)
        self.assertTrue(company.adaptive.enabled)
        self.assertFalse(settings.adaptive.enabled)
        self.assertFalse(company.monitoring.enabled)
        settings.limits.run_usd=0.1
        self.assertEqual(operation_settings(settings,'company').limits.run_usd,0.1)
        settings.adaptive.enabled=True;settings.monitoring.enabled=True
        self.assertEqual(operation_settings(settings,'discovery').model.max_output_tokens,4000)

    def test_calendar_window_and_explicit_backfill(self):
        settings,_=load_settings()
        seeds=seed_queries(settings,'2026-08-31T08:00:00+00:00')
        self.assertEqual(len(seeds),5)
        self.assertTrue(all('after:2026-02-28' in s['query'] for s in seeds))
        settings.company_discovery.include_older=True
        self.assertTrue(all(' after:' not in s['query'] for s in seed_queries(settings,'2026-08-31T08:00:00+00:00')))
        state={'started_at':'2026-08-31T08:00:00+00:00','attempted_queries':[seed_queries(settings,'2026-08-31T08:00:00+00:00')[0]['query']]}
        self.assertNotIn('funding',company_memory(settings,state)['themes_not_attempted'])

    def test_company_run_covers_themes_saves_signals_and_suppresses_job_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);setup(root);queries=[];plans=[]
            text='ExampleCorp announced funding for its production retrieval platform and engineering team.'
            def search(source,query):
                source.searches+=1;queries.append(query)
                url='https://example.com/news/'+str(len(queries))
                source.allowed.add(url);source.cache[query]=[{'url':url}];return source.cache[query]
            def fetch(source,url):
                if url not in source.records:
                    source.fetches+=1
                    source.records[url]={'url':url,'http_status':200,'text':text,'links':[],'source_id':url,'observed_at':'today'}
                return source.records[url]
            def model(settings,prompt,ledger,state,schema=Assessment):
                if schema is ResearchDecision:
                    plans.append(prompt)
                    self.assertIn('COMPANY DISCOVERY OPERATION',prompt)
                    return ResearchDecision(action='finish',explanation='No additional refinements')
                url=state['queue'][len(state['pages_done'])]['url']
                return Assessment(source_type='signal',signals=[Signal(company='ExampleCorp',title='Funding announcement',kind='company',source_id=url,evidence_quote=text,relevance='Retrieval platform matches experience')],findings=[finding()])
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
                _,result=run(root/'config.toml',operation='company')
            self.assertEqual(result['mode'],'company')
            self.assertEqual(result['stop_reason'],'model_finished')
            self.assertEqual(len(queries),5)
            self.assertEqual(len(result['signals']),5)
            self.assertEqual(result['findings'],[])
            self.assertEqual(len([e for e in result['research_trace'] if e['type']=='signal_validation']),5)
            self.assertIn('investigate',next(e['outcome'] for e in result['research_trace'] if e['type']=='signal_validation'))
            self.assertTrue(all('after:' in q for q in queries))
