"""Local scaffold. Demo uses synthetic data and never calls external services."""
import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

PROFILE = {
    "mode": "synthetic-example",
    "locations": ["Germany"],
    "skills": ["Python", "analytics"],
}

def queries():
    return [
        {"track": "ai", "query": '"AI Engineer" "Germany" "English" careers'},
        {"track": "ai", "query": '"RAG" "engineer" "Germany" careers'},
        {"track": "data", "query": '"Data Scientist" "Germany" "English" careers'},
        {"track": "data", "query": '"Data Analyst" "Germany" "English" careers'},
    ]

def save_run(root, payload):
    root.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex
    with closing(sqlite3.connect(root / "jobs.sqlite3")) as db:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT, payload TEXT)")
            db.execute("INSERT INTO runs VALUES (?, ?, ?)",
                       (run_id, datetime.now(timezone.utc).isoformat(), json.dumps(payload)))
    target = root / f"{run_id}.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target

def demo():
    return {"mode": "synthetic-demo", "status": "completed", "profile": PROFILE,
            "queries": queries(), "results": [
                {"company": "SYNTHETIC Example AI", "title": "Applied AI Engineer",
                 "track": "ai", "fit": "possible", "evidence": "Synthetic fixture: RAG, deployment; two years preferred.",
                 "eligibility": "unknown", "live_verified": False},
                {"company": "SYNTHETIC Example Data", "title": "Data Analyst",
                 "track": "data", "fit": "possible", "evidence": "Synthetic fixture: reporting automation; German required.",
                 "language_conflict": True, "eligibility": "unknown", "live_verified": False}],
            "note": "No actual employers or vacancies were searched. No API calls made."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["demo", "plan", "research", "review", "run", "company", "resume", "dashboard", "check", "preview-prompt", "import-history"])
    parser.add_argument("--config",type=Path)
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--run-id")
    parser.add_argument("--provider", choices=["openai", "anthropic"],default="openai")
    parser.add_argument("--model",default="gpt-5-mini")
    parser.add_argument("--run-limit",type=float,default=2)
    parser.add_argument("--max-searches",type=int,default=4)
    parser.add_argument("--output", type=Path, default=Path("runs"))
    args = parser.parse_args()
    if args.command in ("check","preview-prompt"):
        from .settings import load_settings,render_prompt,ROOT
        settings,base=load_settings(args.config)
        prompt=render_prompt(settings,base)
        if args.command=="preview-prompt":
            target=ROOT/"private"/"rendered-prompt.md"; target.parent.mkdir(exist_ok=True)
            target.write_text(prompt,encoding="utf-8"); print(target)
        else:
            print(json.dumps({"valid":True,"provider":settings.model.provider,"model":settings.model.name,"prompt_bytes":len(prompt.encode()),"resume_present":(base/settings.prompts.resume_file).exists(),"max_searches":settings.limits.max_searches}))
        return
    if args.command=="dashboard":
        from .dashboard import serve
        serve(args.port); return
    if args.command=="import-history":
        from .settings import ROOT
        from .catalog import Catalog
        catalog=Catalog(ROOT/"runs"/"catalog.sqlite3"); catalog.import_runs(ROOT/"runs")
        print(f"Imported {len(catalog.list())} unique roles/companies"); return
    if args.command in ("run","company","resume"):
        if args.command=="resume" and not args.run_id: parser.error("resume requires --run-id")
        from .runner import run
        try: folder,result=run(args.config,args.run_id if args.command=="resume" else None,operation="company" if args.command=="company" else "discovery")
        except ValueError as exc: parser.error(str(exc))
        print(json.dumps({"folder":str(folder),"status":result["status"],"findings":len(result["findings"]),"budget":result["budget"]}))
        if result.get("error_type"): raise SystemExit(1)
        return
    if args.command == "review":
        if not args.run_id: parser.error("review requires --run-id")
        from .research import review_saved
        folder,result=review_saved(args.run_id)
        print(json.dumps({"folder":str(folder),"status":result["status"],"findings":len(result["findings"]),"budget":result["budget"]}))
        if result.get("error_type"): raise SystemExit(1)
        return
    if args.command == "research":
        from .research import run_research
        try:
            folder,result=run_research(args.provider,args.model,args.run_limit,args.max_searches)
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({"folder":str(folder),"status":result["status"],"findings":len(result["findings"]),"budget":result["budget"],"error_type":result.get("error_type")}))
        if result.get("error_type"): raise SystemExit(1)
        return
    payload = demo() if args.command == "demo" else {"profile": PROFILE, "queries": queries()}
    print(save_run(args.output, payload))

if __name__ == "__main__":
    main()
