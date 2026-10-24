import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_product import setup
from job_seeker.settings import load_settings
from job_seeker.runner import run,Assessment
from job_seeker.adaptive import ResearchDecision
from job_seeker.clarification import PreferenceCheck,open_question,context
from job_seeker.questions import Questions
from job_seeker.sources import SourceTools
from job_seeker.cloud import pack,unpack


class ClarificationTests(unittest.TestCase):
    def configured(self,root):
        setup(root);settings,_=load_settings(root/'config.toml')
        settings.clarification.enabled=True;settings.adaptive.enabled=True
        settings.notifications.telegram=True
        return settings

    def test_company_preflight_pauses_before_theme_searches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=self.configured(root)
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.load_settings',return_value=(settings,root)),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch('job_seeker.runner.invoke_model',return_value=PreferenceCheck(action='ask_user',topic='geography',question='Should company leads outside Germany be included?',reason='Changes company scope')),patch('job_seeker.clarification.send_question'),patch.object(SourceTools,'search',side_effect=AssertionError('No theme search before answer')):
                folder,result=run(operation='company')
            self.assertEqual(result['mode'],'company');self.assertEqual(result['status'],'waiting_user')
            self.assertEqual(json.loads((folder/'checkpoint.json').read_text())['searches'],0)

    def test_page_assessment_answer_is_available_to_later_assessments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=self.configured(root);plans=[];assessments=[]
            url='https://example.com/role'
            def search(source,query):
                source.searches+=1;source.allowed.add(url);source.cache[query]=[{'url':url}];return source.cache[query]
            def fetch(source,target):
                if target not in source.records:
                    source.fetches+=1;source.records[target]={'url':target,'source_id':'one','http_status':200,'text':'A public role page with responsibilities.','links':[],'observed_at':'today'}
                return source.records[target]
            def model(cfg,prompt,ledger,state,schema=Assessment):
                if schema is PreferenceCheck:return PreferenceCheck(action='ready',reason='Initial scope usable')
                if schema is ResearchDecision:
                    plans.append(prompt)
                    return ResearchDecision(action='research',explanation='Inspect a role',queries=[{'track':'ai','query':'AI jobs'}]) if len(plans)==1 else ResearchDecision(action='finish',explanation='Done')
                assessments.append(prompt)
                if len(assessments)==1:return Assessment(clarification='Would you accept hybrid work?',clarification_reason='Several relevant roles need office attendance')
                self.assertIn('Hybrid is fine',prompt);return Assessment(source_type='unknown')
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.load_settings',return_value=(settings,root)),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch('job_seeker.runner.invoke_model',side_effect=model),patch('job_seeker.clarification.send_question'),patch('job_seeker.telegram.notify'),patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch):
                folder,result=run();self.assertEqual(result['status'],'waiting_user')
                store=Questions(root/'runs/questions.sqlite3');q=store.pending()[0];store.answer(q['id'],q['revision'],'Hybrid is fine')
                _,result=run(resume=folder.name)
            self.assertEqual(result['stop_reason'],'model_finished')
            self.assertIn('Hybrid is fine',json.dumps(store.preferences()))
            self.assertEqual(json.loads((folder/'checkpoint.json').read_text())['fetches'],1)

    def test_preflight_waits_delivers_resumes_and_reuses_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=self.configured(root);calls=[];sent=[]
            def model(cfg,prompt,ledger,state,schema=Assessment):
                calls.append(schema)
                if schema is PreferenceCheck:
                    if calls.count(PreferenceCheck)==1:
                        return PreferenceCheck(action='ask_user',topic='internships',question='Would you consider internships?',reason='Changes which AI opportunities to pursue')
                    self.assertIn('No internships',prompt)
                    return PreferenceCheck(action='ready',reason='Known and saved preferences cover this search')
                self.assertIs(schema,ResearchDecision);self.assertIn('No internships',prompt)
                return ResearchDecision(action='finish',explanation='Test completed')
            def delivery(store,q,on_checkpoint=None):
                if not q['delivered']:sent.append(q['prompt']);store.delivered(q['id'],123)
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.load_settings',return_value=(settings,root)),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch('job_seeker.runner.invoke_model',side_effect=model),patch('job_seeker.clarification.send_question',side_effect=delivery),patch('job_seeker.telegram.notify'),patch.object(SourceTools,'search',side_effect=AssertionError('No search before answer')):
                folder,result=run();self.assertEqual(result['status'],'waiting_user')
                _,again=run(resume=folder.name);self.assertEqual(again['status'],'waiting_user');self.assertEqual(len(calls),1)
                store=Questions(root/'runs/questions.sqlite3');q=store.pending()[0];store.answer(q['id'],q['revision'],'No internships')
                _,result=run(resume=folder.name);self.assertEqual(result['stop_reason'],'model_finished')
                _,result=run();self.assertEqual(result['stop_reason'],'model_finished')
            self.assertEqual(len(sent),1)
            self.assertEqual(store.preferences(),[{'question':'Would you consider internships?','answer':'No internships'}])
            state=json.loads((folder/'checkpoint.json').read_text())
            self.assertEqual(len(state['clarification_questions']),1)
            self.assertNotIn('No internships',json.dumps(state['research_trace']))

    def test_mid_research_question_is_remembered_and_counts_toward_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=self.configured(root);plans=[]
            def model(cfg,prompt,ledger,state,schema=Assessment):
                if schema is PreferenceCheck:return PreferenceCheck(action='ready',reason='Initial scope is usable')
                plans.append(prompt)
                if len(plans)==1:return ResearchDecision(action='ask_user',question='Should repeated senior openings be kept as stretches?',explanation='Recurring seniority ambiguity changes ranking')
                self.assertIn('Keep senior roles as stretches',prompt)
                return ResearchDecision(action='finish',explanation='Done')
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.load_settings',return_value=(settings,root)),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch('job_seeker.runner.invoke_model',side_effect=model),patch('job_seeker.clarification.send_question'),patch('job_seeker.telegram.notify'):
                folder,result=run();self.assertEqual(result['status'],'waiting_user')
                store=Questions(root/'runs/questions.sqlite3');q=store.pending()[0];store.answer(q['id'],q['revision'],'Keep senior roles as stretches')
                _,result=run(resume=folder.name)
            self.assertEqual(result['stop_reason'],'model_finished')
            self.assertEqual(len(store.preferences()),1)
            self.assertEqual(len(json.loads((folder/'checkpoint.json').read_text())['clarification_questions']),1)

    def test_cap_and_duplicate_answers_do_not_create_more_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=self.configured(root);store=Questions(root/'runs/questions.sqlite3')
            state={'run_id':'a'*32,'limitations':[]}
            q=open_question(settings,state,store,'Hybrid?','Scope','one');store.answer(q['id'],q['revision'],'Yes');store.remember(store.get(q['id']))
            self.assertIsNone(open_question(settings,state,store,' HYBRID? ','Scope','two'))
            self.assertIsNotNone(open_question(settings,state,store,'Internships?','Scope','three'))
            self.assertIsNone(open_question(settings,state,store,'Senior roles?','Scope','four'))
            self.assertEqual(len(state['clarification_questions']),2)
            self.assertEqual(len(store.pending()),1)

    def test_monitor_does_not_run_preflight_or_ask_new_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=self.configured(root);settings.monitoring.enabled=True
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.load_settings',return_value=(settings,root)),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch('job_seeker.runner.invoke_model',side_effect=AssertionError('No model for empty saved-source monitoring')),patch('job_seeker.telegram.notify'):
                _,result=run();self.assertEqual(result['status'],'completed')
            state={'run_id':'a'*32,'limitations':[]}
            self.assertIsNone(open_question(settings,state,Questions(root/'runs/questions.sqlite3'),'Hybrid?','Scope','one'))

    def test_memory_is_private_bounded_and_survives_state_archive(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as restored:
            root=Path(tmp);settings=self.configured(root);store=Questions(root/'runs/questions.sqlite3')
            for n in range(8):
                q=store.ask('a'*32,str(n),'Preference '+str(n),'Scope');store.answer(q['id'],q['revision'],'Private answer '+('x'*1800));store.remember(store.get(q['id']))
            text=context(settings,store);self.assertLess(len(text.encode()),6300);self.assertIn('omitted_answers',text)
            unpack(pack(root),Path(restored))
            self.assertEqual(Questions(Path(restored)/'runs/questions.sqlite3').preferences(),store.preferences())
            settings.clarification.reuse_answers=False;self.assertNotIn('Private answer',context(settings,store))
            self.assertIn('Current run answer',context(settings,store,{'candidate_answers':[{'question':'Now?','answer':'Current run answer'}]}))

    def test_explicit_preferences_enter_preflight_and_do_not_require_a_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);settings=self.configured(root);settings.clarification.preferences={'internships':'Exclude internships'}
            def model(cfg,prompt,ledger,state,schema=Assessment):
                self.assertIn('Exclude internships',prompt)
                if schema is PreferenceCheck:
                    self.assertIn('Never ask the candidate whether an employer sponsors visas',prompt)
                    return PreferenceCheck(action='ready',reason='Preferences are sufficiently clear')
                return ResearchDecision(action='finish',explanation='Done')
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.load_settings',return_value=(settings,root)),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch('job_seeker.runner.invoke_model',side_effect=model),patch('job_seeker.telegram.notify'):
                _,result=run()
            self.assertEqual(result['stop_reason'],'model_finished')
            self.assertEqual(Questions(root/'runs/questions.sqlite3').pending(),[])
