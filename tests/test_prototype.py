import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from job_seeker.budget import Ledger, BudgetExceeded
from job_seeker.sources import normalized, public_addresses, SourceTools
from job_seeker.research import Report, Finding, validate_findings, run_research

URL="https://example.org/careers/ai"
QUOTE="Applied AI Engineer: build RAG products and deploy Python services."

def finding(**overrides):
    return Finding(**{**dict(kind="vacancy",track="ai",company="Example",title="Applied AI Engineer",url=URL,
        evidence_quote=QUOTE,fit="possible",fit_reason="RAG overlap",language="unknown",location="unknown",eligibility="unknown",concerns=[]),**overrides})

class Tests(unittest.TestCase):
    def test_each_run_has_its_own_limit_and_history_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"budget.sqlite3"
            for n in range(12): Ledger(p,str(n),.5).reserve("test",.5)
            ledger=Ledger(p,"new",.5);ledger.reserve("test",.5)
            with self.assertRaises(BudgetExceeded): Ledger(p,"new",.5).reserve("test",0.001)
            self.assertEqual(ledger.summary()['total_reserved_usd'],6.5)
            self.assertIsNone(ledger.summary()['review_gate_usd'])

    def test_atomic_reservations(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger=Ledger(Path(temp)/"budget.sqlite3","one",run_limit=0.1)
            def attempt(_):
                try: ledger.reserve("model",0.05); return True
                except BudgetExceeded: return False
            with ThreadPoolExecutor(max_workers=6) as pool:
                self.assertEqual(sum(pool.map(attempt,range(6))),2)

    def test_invalid_budgets(self):
        for value in (0,-1,float("nan"),float("inf")):
            with self.subTest(value=value),tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(ValueError): Ledger(Path(temp)/"b.sqlite3","one",value)

    def test_evidence_rejections_and_deduplication(self):
        record={"http_status":200,"text":QUOTE,"observed_at":"2026-10-23","closed_marker":False}
        good,bad=validate_findings(Report(findings=[finding(),finding(),finding(evidence_quote="A fabricated quote long enough to pass the minimum length")],limitations=[]),{URL:record})
        self.assertEqual(len(good),1); self.assertEqual(len(bad),1)
        record["closed_marker"]=True
        closed,_=validate_findings(Report(findings=[finding()],limitations=[]),{URL:record})
        self.assertEqual(closed[0]['kind'],'excluded');self.assertEqual(closed[0]['listing_status'],'closed')
        self.assertTrue(closed[0]['rejection_reasons'])
        self.assertFalse(validate_findings(Report(findings=[finding()],limitations=[]),{})[0])

    def test_conflicting_fit_never_enters_vacancy_shortlist(self):
        record={"http_status":200,"text":QUOTE,"observed_at":"2026-10-23"}
        good,_=validate_findings(Report(findings=[finding(fit="conflict")],limitations=[]),{URL:record})
        self.assertEqual(good[0]["kind"],"excluded")

    def test_unsafe_urls_and_dns(self):
        for url in ("file:///etc/passwd","http://example.org","https://user:pass@example.org","https://example.org:8443","https://www.linkedin.com/jobs","https://www.linkedin.com./jobs"):
            with self.subTest(url=url),self.assertRaises(ValueError): normalized(url)
        with patch("socket.getaddrinfo",return_value=[(2,1,6,"",("127.0.0.1",443))]):
            with self.assertRaises(ValueError): public_addresses("example.org")

    def test_source_id_resolves_exact_recorded_url(self):
        record={"url":URL,"source_id":"known-source","http_status":200,"text":QUOTE,"observed_at":"2026-10-23","closed_marker":False}
        item=finding(url=URL+"/",source_id="known-source")
        good,bad=validate_findings(Report(findings=[item],limitations=[]),{URL:record})
        self.assertEqual(good[0]["url"],URL); self.assertFalse(bad)
        item.source_id="invented-source"
        self.assertFalse(validate_findings(Report(findings=[item],limitations=[]),{URL:record})[0])

    def test_missing_page_does_not_mean_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            tools=SourceTools(Ledger(Path(temp)/"b.sqlite3","one"),lambda:None)
            tools.allowed.add(URL)
            with patch("job_seeker.sources.public_get",side_effect=[("https://example.org/robots.txt",404,""),(URL,404,"")]):
                record=tools.fetch(URL)
            self.assertEqual(record["http_status"],404)
            self.assertFalse(record["closed_marker"])

    def test_robots_denial(self):
        with tempfile.TemporaryDirectory() as temp:
            tools=SourceTools(Ledger(Path(temp)/"b.sqlite3","one"),lambda:None)
            tools.allowed.add(URL)
            with patch("job_seeker.sources.public_get",return_value=("https://example.org/robots.txt",200,"User-agent: *\nDisallow: /")) as fetch:
                self.assertIn("error",tools.fetch(URL)); self.assertEqual(fetch.call_count,1)

    def test_invalid_site_filter_does_not_spend(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger=Ledger(Path(temp)/"b.sqlite3","one")
            tools=SourceTools(ledger,lambda:None)
            self.assertIn("error",tools.search("Data Scientist site:companies"))
            self.assertEqual(ledger.summary()["reserved_usd"],0)

    def test_service_failure_preserves_budget_and_does_not_fallback(self):
        from job_seeker.sources import ServiceFailure
        def failed_search(self,query):
            self.ledger.reserve("tavily_basic",0.008)
            raise ServiceFailure("Tavily HTTP 401")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"search-profile.md").write_text("Test candidate")
            with patch("job_seeker.research.ROOT",root),patch.dict("os.environ",{"OPENAI_API_KEY":"test-only","TAVILY_API_KEY":"test-only"}),\
                 patch.object(SourceTools,"search",failed_search),patch("langchain_openai.ChatOpenAI") as model:
                folder,result=run_research()
            self.assertEqual(result["status"],"failed")
            self.assertEqual(result["error_type"],"ServiceFailure")
            self.assertEqual(result["budget"]["unreconciled_calls"],1)
            model.assert_not_called()
            self.assertIn("401",result["limitations"][0])

    def test_real_agent_graph_with_fake_model_and_sources(self):
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        class FakeModel(BaseChatModel):
            step: int=0
            @property
            def _llm_type(self): return "offline-test"
            def bind_tools(self,tools,**kwargs): return self
            def _generate(self,messages,stop=None,run_manager=None,**kwargs):
                self.step+=1
                name,args=[("search_web",{"query":"AI Engineer Germany"}),
                           ("read_source",{"url":URL}),
                           ("Report",{"findings":[finding().model_dump()],"limitations":["Synthetic integration test"]})][self.step-1]
                msg=AIMessage(content="",tool_calls=[{"name":name,"args":args,"id":str(self.step)}],
                              usage_metadata={"input_tokens":100,"output_tokens":50,"total_tokens":150})
                return ChatResult(generations=[ChatGeneration(message=msg)])
        def fake_search(self,query):
            self.allowed.add(URL); self.persist(); return [{"url":URL,"title":"Example","snippet":QUOTE}]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"search-profile.md").write_text("Test candidate: RAG.")
            with patch("job_seeker.research.ROOT",root),patch.dict("os.environ",{"OPENAI_API_KEY":"test-only","TAVILY_API_KEY":"test-only"}),\
                 patch("langchain_openai.ChatOpenAI",return_value=FakeModel()),patch.object(SourceTools,"search",fake_search),\
                 patch("job_seeker.sources.public_get",side_effect=[("https://example.org/robots.txt",404,""),(URL,200,"<p>"+QUOTE+"</p>")]):
                folder,result=run_research()
            self.assertEqual(result["status"],"completed",result)
            self.assertEqual(len(result["findings"]),1)
            self.assertAlmostEqual(result["budget"]["reserved_usd"],0.15)
            self.assertTrue((folder/"evidence.json").exists())
            self.assertNotIn("test-only",(folder/"result.json").read_text())

    def test_saved_review_uses_same_budget_and_no_search(self):
        from job_seeker.research import review_saved
        from langchain_core.messages import AIMessage
        run_id="a"*32
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); folder=root/"runs"/run_id; folder.mkdir(parents=True)
            (root/"search-profile.md").write_text("Candidate: RAG")
            (folder/"result.json").write_text(json.dumps({"provider":"openai","model":"gpt-5-mini","run_limit_usd":0.1}))
            (folder/"evidence.json").write_text(json.dumps({"sources":{URL:{"url":URL,"http_status":200,"text":QUOTE,"observed_at":"2026-10-23"}}}))
            ledger=Ledger(root/"runs"/"budget.sqlite3",run_id,0.1)
            ledger.reserve("earlier",0.05)
            reply={"parsed":Report(findings=[finding()],limitations=[]),
                   "raw":AIMessage(content="",usage_metadata={"input_tokens":100,"output_tokens":50,"total_tokens":150})}
            with patch("job_seeker.research.ROOT",root),patch.dict("os.environ",{"OPENAI_API_KEY":"test-only"}),\
                 patch("langchain_openai.ChatOpenAI") as model,patch.object(SourceTools,"search") as search:
                model.return_value.with_structured_output.return_value.invoke.return_value=reply
                _,result=review_saved(run_id)
                self.assertEqual(len(result["findings"]),1)
                self.assertEqual(result["budget"]["reserved_usd"],0.1)
                with self.assertRaises(BudgetExceeded): review_saved(run_id)
                search.assert_not_called()

if __name__=="__main__": unittest.main()
