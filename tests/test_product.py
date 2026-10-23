import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from job_seeker.settings import load_settings,render_prompt,Settings,ModelSettings
from job_seeker.catalog import Catalog
from job_seeker.cloud import pack,unpack
from job_seeker.runner import run,Assessment,single_worker
from job_seeker.sources import SourceTools
from test_prototype import finding,URL,QUOTE

PROJECT=Path(__file__).resolve().parent.parent

def setup(root):
    (root/'private').mkdir(); (root/'prompts').mkdir()
    (root/'config.toml').write_text((PROJECT/'config.toml').read_text())
    (root/'private/profile.md').write_text('Candidate with RAG and analytics experience. German basic.')
    (root/'prompts/master.md').write_text('PROFILE {{profile}} RESUME {{resume}}')

class ProductTests(unittest.TestCase):
    def test_mandatory_conflict_overrides_technical_fit(self):
        from job_seeker.research import validate_findings,Report
        good,_=validate_findings(Report(findings=[finding(fit='strong',mandatory_conflicts=['German communication required'])],limitations=[]),
            {URL:{'http_status':200,'text':QUOTE,'observed_at':'today'}})
        self.assertEqual(good[0]['kind'],'excluded')
    def test_resume_rendering_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); setup(root)
            config,base=load_settings(root/'config.toml')
            self.assertIn('No resume supplied',render_prompt(config,base))
            (root/'private/resume.md').write_text('Actual project {{profile}}')
            rendered=render_prompt(config,base)
            self.assertIn('Actual project {{profile}}',rendered)
            config.prompts.resume_file='../outside.md'
            with self.assertRaises(ValueError): render_prompt(config,base)
            with self.assertRaises(ValueError): ModelSettings(input_usd_per_million=0.01)

    def test_rejections_and_human_decisions_survive_new_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Catalog(Path(tmp)/'jobs.sqlite3')
            item=finding(kind='excluded',fit='conflict').model_dump()
            item['rejection_reasons']=['German required']
            store.ingest('one',[item]); ident=store.list()[0]['id']
            store.decide(ident,'apply_anyway','I will ask about English teams')
            store.ingest('two',[{**item,'fit_reason':'Updated assessment'}])
            rows=store.list(); self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['decision'],'apply_anyway')
            self.assertEqual(rows[0]['rejection_reasons'],['German required'])
            self.assertEqual(rows[0]['kind'],'excluded')

    def test_cloud_archive_excludes_secrets_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); setup(root); (root/'.env').write_text('SECRET=never-export')
            (root/'runs').mkdir(); (root/'runs/worker.lock').write_text('lock')
            data=pack(root)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                self.assertNotIn('.env',z.namelist()); self.assertNotIn('runs/worker.lock',z.namelist())
                self.assertIn('private/profile.md',z.namelist())
            bad=io.BytesIO()
            with zipfile.ZipFile(bad,'w') as z: z.writestr('../outside','bad')
            with self.assertRaises(ValueError): unpack(bad.getvalue(),root)

    def test_clarification_waits_then_resumes_with_answer(self):
        from job_seeker.questions import Questions
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); setup(root); calls=[]
            def search(source,query):
                source.allowed.add(URL); source.cache[query]=[{'url':URL}]; return source.cache[query]
            def fetch(source,url):
                source.records[url]={'url':URL,'http_status':200,'text':QUOTE,'source_id':'known','observed_at':'today','links':[]}; source.fetches=1; return source.records[url]
            def model(config,prompt,ledger,state):
                calls.append(prompt)
                if len(calls)==1: return Assessment(clarification='Would you accept hybrid work?',clarification_reason='Needed for fit')
                self.assertIn('Yes, hybrid is fine',prompt)
                return Assessment(findings=[finding(source_id='known')])
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
                folder,result=run(root/'config.toml'); self.assertEqual(result['status'],'waiting_user')
                _,result=run(resume=folder.name); self.assertEqual(result['status'],'waiting_user'); self.assertEqual(len(calls),1)
                store=Questions(root/'runs/questions.sqlite3'); q=store.pending()[0]
                store.answer(q['id'],q['revision'],'Yes, hybrid is fine')
                _,result=run(resume=folder.name); self.assertEqual(result['status'],'completed',result); self.assertEqual(len(calls),2)

    def test_worker_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            with single_worker(Path(tmp)):
                with self.assertRaises(ValueError):
                    with single_worker(Path(tmp)): pass
            with single_worker(Path(tmp)): pass

    def test_restart_does_not_repeat_completed_search_or_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); setup(root)
            searches=[]; calls=[]
            def search(source,query):
                if query in source.cache: return source.cache[query]
                searches.append(query); source.searches+=1; source.allowed.add(URL)
                source.cache[query]=[{'url':URL,'title':'Applied AI Engineer'}]; source.persist()
                return source.cache[query]
            def fetch(source,url):
                if url not in source.records:
                    source.fetches+=1; source.records[url]={'url':url,'source_id':'known','http_status':200,'text':QUOTE,'observed_at':'today','links':[]}
                    source.persist()
                return source.records[url]
            def model(config,prompt,ledger,state):
                calls.append(prompt)
                return Assessment(findings=[finding(fit='conflict',source_id='known')],rejection_reasons=['German required'])
            with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'fake','TAVILY_API_KEY':'fake'}),\
                 patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
                folder,result=run(root/'config.toml')
                self.assertEqual(result['status'],'completed',result)
                self.assertEqual(result['findings'][0]['kind'],'excluded')
                self.assertEqual(len(calls),1)
                # Simulate a crash after checkpoint but before the final report write.
                (folder/'result.json').unlink()
                _,result2=run(resume=folder.name)
                self.assertEqual(result2['status'],'completed')
                self.assertEqual(len(calls),1); self.assertEqual(len(searches),6)
                self.assertEqual(len(Catalog(root/'runs/catalog.sqlite3').list()),1)
                self.assertTrue((folder/'prompt.md').exists())

if __name__=='__main__': unittest.main()
