import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from job_seeker import telemetry as audit
from job_seeker.budget import Ledger,BudgetExceeded
from job_seeker.sources import SourceTools
from job_seeker.settings import load_settings
from job_seeker.runner import invoke_model,Assessment
from job_seeker.cloud import pack,unpack


def fixture_run(root):
    """Exercise real runner/tool/model wrappers with synthetic external responses."""
    from test_product import setup
    from test_prototype import finding,QUOTE,URL
    from job_seeker.adaptive import ResearchDecision
    from job_seeker.runner import run
    import hashlib
    setup(root)
    config=root/'config.toml'
    config.write_text(config.read_text().replace('enabled=false','enabled=true'),encoding='utf-8')
    plans=[];pages=[]
    def generate(schema,prompt):
        if schema is ResearchDecision:
            plans.append(prompt)
            if len(plans)==1:
                output=ResearchDecision(action='research',explanation='Initial synthetic search',queries=[{'track':'ai','query':'AI Germany'}])
            elif len(plans)==2:
                current=json.loads(next((root/'runs').glob('*/evaluation.json')).read_text(encoding='utf-8'))
                output=ResearchDecision(action='research',explanation='Try an early-career title',queries=[{'track':'ai','query':'junior AI Germany'}],query_notes=[{'query':'junior AI Germany','parent_search_id':current['searches'][0]['id'],'change_reason':'Test early-career wording','expected_improvement':'Find an additional role','target_country':'Germany','strategy':'early_career'}])
            else:output=ResearchDecision(action='finish',explanation='Synthetic acceptance complete')
        else:
            url=URL if not pages else URL+'/second';pages.append(url)
            output=Assessment(source_type='employer',findings=[finding(url=url,title='RAG Engineer' if len(pages)==1 else 'Junior RAG Engineer',source_id=hashlib.sha256(url.encode()).hexdigest()[:16])])
        return {'parsed':output,'raw':SimpleNamespace(usage_metadata={'input_tokens':100,'output_tokens':20})}
    def retrieve(url):
        if url.endswith('/robots.txt'):return url,404,''
        return url,200,'<h1>'+('Junior RAG Engineer' if url.endswith('/second') else 'RAG Engineer')+'</h1><p>'+QUOTE+'</p>'
    def post(*args,**kwargs):
        url=URL if kwargs['json']['query']=='AI Germany' else URL+'/second'
        return httpx.Response(200,json={'results':[{'url':url,'title':'Synthetic vacancy','content':'Synthetic search result'}],'usage':{'credits':1}})
    with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch('job_seeker.sources._public_get',side_effect=retrieve),patch('httpx.Client') as client,patch('langchain_openai.ChatOpenAI') as model:
        client.return_value.__enter__.return_value.post.side_effect=post
        model.return_value.with_structured_output.side_effect=lambda schema,**kwargs:SimpleNamespace(invoke=lambda prompt:generate(schema,prompt))
        return run(config)


def state(root):
    return {'run_id':'a'*32,'folder':str(root/'runs'/('a'*32)),'mode':'discovery',
            'status':'running','model_calls':0,'usage':[],'api_log':[],'search_log':[],
            'sources':{},'findings':[],'signals':[],'pages_done':[]}


class TelemetryTests(unittest.TestCase):
    def test_resume_preserves_receipt_newer_than_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp,audit.session():
            s=state(Path(tmp));audit.bind(s);row=audit.search_start(s,'AI Poland')
            checkpoint=json.loads(json.dumps(s))
            audit.finish(s,row,'success',observed_estimate_usd=.008,results=[])
            audit.bind(checkpoint)
            self.assertEqual(checkpoint['search_log'][0]['status'],'success')
            self.assertEqual(audit.snapshot(checkpoint)['by_purpose']['tavily:search']['observed_estimate_usd'],.008)
    def test_full_adaptive_run_links_revision_to_two_validated_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,result=fixture_run(Path(tmp))
            self.assertEqual(result['status'],'completed')
            report=json.loads((folder/'evaluation.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report['searches']),2)
            self.assertEqual(report['searches'][1]['parent_search_id'],report['searches'][0]['id'])
            self.assertEqual(report['searches'][1]['metrics']['additional_vacancies'],1)
            self.assertEqual(len(report['findings']),2)
            self.assertEqual(report['by_purpose']['openai:planning']['attempts'],3)
            self.assertEqual(report['by_purpose']['openai:page_assessment']['attempts'],2)
            self.assertEqual(len(report['plans']),3)
    def test_complete_search_results_revision_and_distinct_contribution(self):
        with tempfile.TemporaryDirectory() as tmp,audit.session():
            root=Path(tmp);s=state(root);audit.bind(s)
            tools=SourceTools(Ledger(root/'budget.sqlite3',s['run_id'],.5),lambda:None)
            tools.audit_state=s
            bodies=[{'results':[{'url':'https://example.com/a','title':'A','content':'first snippet'},{'url':'https://example.com/b','title':'B','content':'unread snippet'}]},
                    {'results':[{'url':'https://example.com/a','title':'A','content':'overlap'},{'url':'https://example.com/c','title':'C','content':'full '*500},{'url':'http://blocked.example/job','title':'Rejected','content':'kept for diagnostics'}]}]
            def post(*args,**kwargs):
                # Receipt is durable before any provider execution.
                saved=json.loads((Path(s['folder'])/'evaluation.json').read_text(encoding='utf-8'))
                self.assertEqual(saved['searches'][-1]['status'],'started')
                return httpx.Response(200,json=bodies.pop(0))
            with patch.dict('os.environ',{'TAVILY_API_KEY':'SECRET-API-CREDENTIAL'}),patch('httpx.Client') as client:
                client.return_value.__enter__.return_value.post.side_effect=post
                tools.search('AI Poland')
                parent=s['search_log'][0]['id']
                s['active_round']={'decision':{'explanation':'Reduce seniority','query_notes':[{'query':'junior AI Poland','parent_search_id':parent,'change_reason':'Senior-only results','expected_improvement':'Early-career vacancies','target_country':'Poland'}]},'actions':{'queries':[{'query':'junior AI Poland','track':'ai'}]}}
                tools.search('junior AI Poland')
                tools.search('junior AI Poland')
                tools.search('site:example.com/path invalid')
            for suffix in ('a','c'):
                url='https://example.com/'+suffix;s['sources'][url]={'http_status':200,'links':[]};s['pages_done'].append(url)
                s['findings'].append({'url':url,'title':suffix,'kind':'vacancy'})
            s['api_log'].append({'id':'model-call','provider':'openai','purpose':'page_assessment','status':'success','url':'https://example.com/a','observed_estimate_usd':.01})
            report=audit.snapshot(s)
            self.assertEqual(report['searches'][1]['parent_search_id'],parent)
            self.assertEqual(report['searches'][1]['metrics']['additional_vacancies'],1)
            self.assertEqual(report['searches'][0]['metrics']['unread_result_urls'],1)
            self.assertEqual(report['searches'][0]['linked_model_call_ids'],['model-call'])
            self.assertEqual(report['searches'][1]['linked_model_call_ids'],['model-call'])
            self.assertEqual(report['by_purpose']['openai:page_assessment']['observed_estimate_usd'],.01)
            self.assertEqual(report['searches'][1]['results'][1]['snippet'],'full '*500)
            self.assertFalse(report['searches'][1]['results'][2]['accepted'])
            self.assertEqual(report['searches'][2]['status'],'cached')
            self.assertEqual(report['searches'][2]['metrics']['additional_vacancies'],0)
            self.assertEqual(report['searches'][3]['status'],'rejected')
            self.assertEqual(tools.searches,2)
            self.assertAlmostEqual(report['by_purpose']['tavily:search']['observed_estimate_usd'],.016)
            self.assertNotIn('SECRET-API-CREDENTIAL',json.dumps(report))

    def test_parent_must_be_observed_and_started_call_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp,audit.session():
            s=state(Path(tmp));audit.bind(s)
            s['active_round']={'decision':{'query_notes':[{'query':'AI jobs','parent_search_id':'invented'}]}}
            audit.search_start(s,'AI jobs')
            saved=json.loads((Path(s['folder'])/'evaluation.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['searches'][0]['status'],'started')
            self.assertIsNone(saved['searches'][0]['parent_search_id'])
            self.assertFalse(saved['searches'][0]['parent_reference_valid'])
            self.assertEqual(saved['by_purpose']['tavily:search']['cost_unknown_calls'],1)

    def test_model_usage_and_failure_receipts_omit_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=state(root);settings,_=load_settings()
            ledger=Ledger(root/'budget.sqlite3',s['run_id'],.5)
            reply={'raw':SimpleNamespace(usage_metadata={'input_tokens':100,'output_tokens':20,'output_token_details':{'reasoning':10}}),'parsed':Assessment()}
            with patch('langchain_openai.ChatOpenAI') as model:
                invoke=model.return_value.with_structured_output.return_value.invoke
                invoke.return_value=reply
                invoke_model(settings,'SECRET CANDIDATE INPUT',ledger,s)
                invoke.side_effect=RuntimeError('Sensitive provider error body')
                with self.assertRaises(RuntimeError):invoke_model(settings,'SECRET CANDIDATE INPUT',ledger,s)
            report=audit.snapshot(s)
            self.assertEqual(report['calls'][0]['purpose'],'page_assessment')
            self.assertEqual(report['calls'][0]['reasoning_tokens'],10)
            self.assertEqual(report['calls'][1]['status'],'failed')
            self.assertEqual(report['by_purpose']['openai:page_assessment']['cost_unknown_calls'],1)
            self.assertNotIn('SECRET CANDIDATE INPUT',json.dumps(report))
            self.assertNotIn('Sensitive provider error body',json.dumps(report))
            self.assertEqual(ledger.summary()['unreconciled_calls'],1)

    def test_blocked_model_input_is_not_charged_and_csv_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=state(root);settings,_=load_settings();ledger=Ledger(root/'budget.sqlite3',s['run_id'],.5)
            with self.assertRaises(BudgetExceeded):invoke_model(settings,'x'*90000,ledger,s)
            self.assertEqual(s['api_log'][0]['status'],'blocked')
            self.assertEqual(s['api_log'][0]['observed_estimate_usd'],0)
            self.assertEqual(ledger.summary()['reserved_usd'],0)
            report={'searches':[{'query':'=HYPERLINK("bad")','metrics':{'additional_vacancies':1}}]}
            self.assertIn("'=HYPERLINK",audit.csv_report(report))

    def test_evaluation_is_in_private_backup_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=state(root);audit.save(s)
            data=pack(root);destination=root/'restored';unpack(data,destination)
            saved=json.loads((destination/'runs'/s['run_id']/'evaluation.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['run_id'],s['run_id'])
            self.assertEqual(saved['schema_version'],1)

    def test_http_retrieval_has_status_and_duration_without_body(self):
        with tempfile.TemporaryDirectory() as tmp,audit.session():
            s=state(Path(tmp));audit.bind(s)
            from job_seeker.sources import public_get
            with patch('job_seeker.sources._public_get',return_value=('https://example.com/job',200,'PAGE BODY')):
                public_get('https://example.com/job')
            row=s['api_log'][0]
            self.assertEqual(row['purpose'],'public_retrieval')
            self.assertEqual(row['http_status'],200)
            self.assertIn('duration_ms',row)
            self.assertNotIn('PAGE BODY',json.dumps(row))
