import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_product import setup
from job_seeker.runner import run,Assessment
from job_seeker.adaptive import ResearchDecision
from job_seeker.sources import SourceTools
from job_seeker.questions import Questions


class AdaptiveRunnerTests(unittest.TestCase):
    def test_final_fetched_page_is_assessed_before_resource_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);assessed=[]
            config,_,search,fetch=self.exercise(root,None)
            config.write_text(config.read_text().replace('max_searches = 6','max_searches = 1').replace('max_pages = 12','max_pages = 1'))
            def model(config,prompt,ledger,state,schema=Assessment):
                if schema is ResearchDecision:return ResearchDecision(action='research',explanation='Inspect one page',queries=[{'track':'ai','query':'RAG Germany'}])
                assessed.append(prompt);return Assessment(source_type='index')
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
                _,result=run(config)
            self.assertEqual(len(assessed),1)
            self.assertEqual(result['stop_reason'],'research_resources_exhausted')
            self.assertIsNone(result.get('error_type'))

    def test_failed_search_page_replans_then_navigates_careers_to_posting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plans=[]; read=[]
            config,_,_,_=self.exercise(root,None)
            def search(source,query):
                url='https://example.com/expired' if not source.cache else 'https://example.com/careers'
                source.searches+=1;source.allowed.add(url);source.cache[query]=[{'url':url}]
                return source.cache[query]
            def fetch(source,url):
                if url not in source.records:
                    source.fetches+=1;read.append(url)
                    page={'url':url,'http_status':410 if url.endswith('expired') else 200,'text':'Individual listing requires inspection.','source_id':url,'observed_at':'today','links':[]}
                    if url.endswith('careers'):page.update(structured_index=True,links=['https://example.com/jobs/123'])
                    source.records[url]=page
                return source.records[url]
            def model(config,prompt,ledger,state,schema=Assessment):
                if schema is not ResearchDecision:return Assessment(source_type='employer')
                plans.append(prompt)
                if len(plans)==1:return ResearchDecision(action='research',explanation='Start search',queries=[{'track':'ai','query':'AI engineer Germany'}])
                if len(plans)==2:
                    self.assertIn('410',prompt);self.assertIn('machine learning engineer',prompt)
                    return ResearchDecision(action='research',explanation='Change role and source',queries=[{'track':'ai','query':'junior machine learning engineer Germany careers'}])
                if len(plans)==3:return ResearchDecision(action='research',explanation='Inspect discovered posting',inspect_urls=['https://example.com/jobs/123'])
                return ResearchDecision(action='finish',explanation='Test complete')
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
                _,result=run(config)
            self.assertEqual(read,['https://example.com/expired','https://example.com/careers','https://example.com/jobs/123'])
            self.assertEqual(result['stop_reason'],'model_finished')

    def test_planning_reservation_failure_prevents_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            config,_,_,_=self.exercise(root,None)
            config.write_text(config.read_text().replace('run_usd = 2.0','run_usd = 0.001'))
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch.object(SourceTools,'search',side_effect=AssertionError('No search before reservation')):
                _,result=run(config)
            self.assertEqual(result['error_type'],'BudgetExceeded')
            self.assertEqual(result['stop_reason'],'budget_or_model_limit')
            self.assertEqual(result['usage'],[])

    def exercise(self,root,model):
        setup(root)
        config = root/'config.toml'
        config.write_text(config.read_text().replace('enabled=false','enabled=true').replace('pages_per_round = 6','pages_per_round = 1'))
        searched = []
        def search(source,query):
            if query not in source.cache:
                source.searches += 1
                searched.append(query)
                url = 'https://example.com/'+str(len(searched))
                source.allowed.add(url);source.cache[query]=[{'url':url}]
            return source.cache[query]
        def fetch(source,url):
            if url not in source.records:
                source.fetches += 1
                source.records[url]={'url':url,'http_status':200,'text':'No individual vacancy on this page.','source_id':url,'observed_at':'today','links':[]}
            return source.records[url]
        return config,searched,search,fetch

    def test_replans_after_inspection_and_uses_medium_then_high(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plans=[]; efforts=[]
            def model(config,prompt,ledger,state,schema=Assessment):
                if schema is ResearchDecision:
                    plans.append(prompt)
                    if len(plans)==3: return ResearchDecision(action='finish',explanation='Coverage complete')
                    return ResearchDecision(action='research',explanation='Try a different title',queries=[{'track':'ai','query':'query '+str(len(plans))}],use_high_reasoning=len(plans)==2)
                efforts.append(config.model.reasoning_effort)
                return Assessment(source_type='index')
            config,searched,search,fetch=self.exercise(root,model)
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
                folder,result=run(config)
            self.assertEqual(searched,['query 1','query 2'])
            self.assertEqual(efforts,['medium','high'])
            self.assertIn('https://example.com/1',plans[1])
            self.assertEqual(result['stop_reason'],'no_progress')  # Two inspected rounds with no useful records.
            self.assertEqual(len([t for t in result['research_trace'] if t['type']=='page']),2)
            receipts=[t for t in result['research_trace'] if t['type']=='search_end']
            self.assertEqual(receipts[0]['result_count'],1)
            self.assertEqual(receipts[0]['urls'],['https://example.com/1'])
            self.assertEqual(result['research_trace'][0]['type'],'plan')

    def test_planner_question_resumes_without_replanning_or_searching_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); calls=[]
            def model(config,prompt,ledger,state,schema=Assessment):
                calls.append(prompt)
                if len(calls)==1: return ResearchDecision(action='ask_user',explanation='Location preference changes scope',question='Would you accept hybrid?')
                self.assertIn('Yes, hybrid',prompt)
                return ResearchDecision(action='finish',explanation='Test completed')
            config,searched,search,fetch=self.exercise(root,model)
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
                folder,result=run(config)
                self.assertEqual(result['status'],'waiting_user')
                _,result=run(resume=folder.name)
                self.assertEqual(len(calls),1)
                store=Questions(root/'runs/questions.sqlite3');q=store.pending()[0]
                store.answer(q['id'],q['revision'],'Yes, hybrid')
                _,result=run(resume=folder.name)
            self.assertEqual(result['stop_reason'],'model_finished')
            self.assertEqual(searched,[])
            self.assertEqual(len(calls),2)

    def test_interrupted_search_keeps_admitted_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); calls=[]
            def model(config,prompt,ledger,state,schema=Assessment):
                if schema is ResearchDecision:
                    calls.append(prompt)
                    return ResearchDecision(action='research',explanation='Inspect roles',queries=[{'track':'ai','query':'RAG Germany'}]) if len(calls)==1 else ResearchDecision(action='finish',explanation='Done')
                return Assessment(source_type='index')
            config,searched,search,fetch=self.exercise(root,model)
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
                with patch.object(SourceTools,'search',side_effect=RuntimeError('interrupted')):
                    folder,result=run(config)
                self.assertEqual(len(calls),1)
                with patch.object(SourceTools,'search',search): _,result=run(resume=folder.name)
            self.assertEqual(searched,['RAG Germany'])
            self.assertEqual(len(calls),2)
            self.assertEqual(result['stop_reason'],'model_finished')
