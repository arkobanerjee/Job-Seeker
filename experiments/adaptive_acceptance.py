"""Explicit isolated, paid acceptance of the production runner. No cloud writes."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import uuid4
from .comparison import HOME,safe_home,save
from job_seeker.budget import Ledger
from job_seeker.runner import run,invoke_model,Assessment,POLICY,single_worker
from job_seeker.settings import ROOT,load_settings,render_prompt
from job_seeker.signals import validate_signals
from job_seeker.research import Report,validate_findings


def metrics(folder,result,elapsed):
    state=json.loads((folder/'checkpoint.json').read_text(encoding='utf-8'))
    findings=result['findings'];signals=result['signals']
    qualified={s['company'].casefold() for s in signals if s.get('qualification_status')=='qualified'}
    return {'status':result['status'],'error_type':result.get('error_type'),'stop_reason':result.get('stop_reason'),
            'elapsed_s':round(elapsed,2),'searches':state['searches'],'pages':state['fetches'],'model_calls':state['model_calls'],
            'unavailable_pages':sum(s.get('http_status')!=200 for s in state['sources'].values()),
            'vacancies':sum(f['kind']=='vacancy' for f in findings),'excluded':sum(f['kind']=='excluded' for f in findings),
            'distinct_vacancies':len({(f['url'],f['title']) for f in findings if f['kind']=='vacancy'}),
            'qualified_companies':len(qualified),
            'investigation_companies':len({s['company'].casefold() for s in signals if s.get('qualification_status')!='qualified'}-qualified),
            'rounds':state.get('rounds',0),'trace_events':len(state.get('research_trace',[])),
            'budget':result['budget'],'result_path':str(folder/'result.json')}


def frozen(settings,base,target,cap=.4):
    """Reference labels are frozen here and never sent to the assessor."""
    folder=target/'frozen';folder.mkdir()
    config=settings.model_copy(deep=True);config.adaptive.enabled=False
    config.model.reasoning_effort='medium';config.limits.run_usd=cap
    config.limits.max_model_calls=12
    ledger=Ledger(HOME/'budget.sqlite3',uuid4().hex,cap)
    state={'folder':str(folder),'model_calls':0,'usage':[]}
    background=render_prompt(config,base)
    cases=json.loads((ROOT/'tests/fixtures/quality_cases.json').read_text())
    selected=[c for c in cases if c['id'] in ['ai_rag','german_mandatory','visa_unknown','index']]
    company_cases=[
        ('funding','Futura raised funding to deploy its RAG platform in production.',True),
        ('biography','Futura is the author of an article introducing RAG terminology.',False),
        ('negated','Futura has not raised funding and is not hiring for its RAG platform.',False),
        ('product','Futura launched a new RAG platform for production customers.',True)]
    save(folder/'reference-labels.json',{'jobs':{c['id']:c['expected'] for c in selected},'companies':{i:expected for i,_,expected in company_cases}})
    predictions=[]
    for case in selected:
        page={**case['source'],'links':[]}
        assessment=invoke_model(config,POLICY+'\n'+background+'\nSOURCE DATA:\n'+json.dumps(page),ledger,state)
        good,bad=validate_findings(Report(findings=[] if assessment.source_type=='index' else assessment.findings,limitations=[]),{page['url']:page})
        expected=case['expected']['kind']
        passed=(not any(f['kind']=='vacancy' for f in good)) if expected=='unverified' else any(f['kind']==expected for f in good)
        for field in case['expected']['unknown_fields']:
            if good and any(f[field]!='unknown' for f in good):passed=False
        predictions.append({'id':case['id'],'passed':passed,'assessment':assessment.model_dump(),'checked':good,'rejected':bad})
        save(folder/'predictions.json',predictions)
    for ident,text,expected in company_cases:
        page={'source_id':ident,'url':'https://synthetic.example/'+ident,'http_status':200,'text':text,'observed_at':'2026-10-24T00:00:00+00:00','links':[]}
        assessment=invoke_model(config,POLICY+'\n'+background+'\nExtract only company signals from this supplied synthetic page. Distinguish concrete events from generic or negated claims. No vacancies.\nSOURCE DATA:\n'+json.dumps(page),ledger,state)
        good,bad=validate_signals(assessment.signals,page,'frozen',background)
        promoted=any(s['qualification_status']=='qualified' for s in good)
        predictions.append({'id':ident,'passed':promoted==expected,'assessment':assessment.model_dump(),'checked':good,'rejected':bad})
        save(folder/'predictions.json',predictions)
    result={'cases':len(predictions),'passed':sum(p['passed'] for p in predictions),'budget':ledger.summary()}
    save(folder/'report.json',result);return result


def execute(cap=.4):
    if os.environ.get('COMPARISON_CHILD')!='1':raise ValueError('Use isolated launcher')
    if any(('TOKEN' in k or 'KEY' in k or k.startswith('JOB_SEEKER')) and k not in {'OPENAI_API_KEY','TAVILY_API_KEY'} for k in os.environ):raise ValueError('Unexpected credentials')
    safe_home(HOME)
    settings,base=load_settings()
    settings.notifications.telegram=False;settings.monitoring.enabled=False;settings.monitoring.schedule_enabled=False
    settings.review.enabled=False;settings.corroboration.enabled=False;settings.competitors.enabled=False
    settings.model.max_output_tokens=8000
    settings.limits.max_searches=6;settings.limits.max_pages=8;settings.limits.max_model_calls=12;settings.limits.run_usd=cap
    settings.adaptive.queries_per_round=2;settings.adaptive.pages_per_round=2
    settings.company_discovery.max_searches=6;settings.company_discovery.max_pages=8
    settings.company_discovery.max_model_calls=12;settings.company_discovery.run_usd=cap
    with single_worker(HOME):
        allocation=HOME/'adaptive-allowance.json'
        if not allocation.exists():save(allocation,{'starting_reserved_usd':Ledger(HOME/'budget.sqlite3','probe',cap).summary()['initial_stage_reserved_usd'],'additional_ceiling_usd':2.8})
        allowed=json.loads(allocation.read_text())
        projected=Ledger(HOME/'budget.sqlite3','acceptance-preflight',cap).summary()['initial_stage_reserved_usd']+4*cap+.25
        if projected>min(5,allowed['starting_reserved_usd']+allowed['additional_ceiling_usd']):raise ValueError('Acceptance does not fit remaining experiment allowance')
        target=HOME/'adaptive'/uuid4().hex;target.mkdir(parents=True)
        save(target/'manifest.json',{'settings':settings.model_dump(),'arms':['fixed_vacancy','adaptive_company','adaptive_vacancy','fixed_mixed_company'],
             'maximum_reserved_usd':4*cap+.25,'production_access':False,
             'code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'job_seeker').glob('*.py')}})
        print('Acceptance artifacts: '+str(target),flush=True)
        frozen_result=frozen(settings,base,target,.25)
        print('Frozen checks: '+str(frozen_result['passed'])+'/'+str(frozen_result['cases']),flush=True)
        results=[]
        original_ledger=Ledger
        for arm in ['fixed_vacancy','adaptive_company','adaptive_vacancy','fixed_mixed_company']:
            root=target/arm;root.mkdir()
            cfg=settings.model_copy(deep=True)
            cfg.adaptive.enabled=arm.startswith('adaptive')
            cfg.signals.enabled=arm=='fixed_mixed_company'
            if cfg.signals.enabled:cfg.signals.max_queries=2
            # Freeze the exact background in each arm; do not copy .env or cloud state.
            for name in [cfg.prompts.master_file,cfg.prompts.profile_file,cfg.prompts.resume_file]:
                source=base/name
                if source.exists():
                    dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
            started=time.monotonic()
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.load_settings',return_value=(cfg,root)),patch('job_seeker.runner.Ledger',side_effect=lambda path,ident,cap:original_ledger(HOME/'budget.sqlite3',ident,cap)):
                folder,result=run(operation='company' if arm=='adaptive_company' else 'discovery')
            row={'arm':arm,**metrics(folder,result,time.monotonic()-started)};results.append(row)
            save(target/'results.json',results)
            print(json.dumps({k:v for k,v in row.items() if k not in ('budget','result_path')}),flush=True)
        return target


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--child',action='store_true');parser.add_argument('--resume-batch');parser.add_argument('--vacancy-pair',action='store_true')
    args=parser.parse_args()
    if not args.live:raise ValueError('Explicit --live required; use unit tests for offline checks')
    if not args.child:
        from dotenv import dotenv_values
        values=dotenv_values(ROOT/'.env')
        env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','COMSPEC','PATHEXT','SYSTEMDRIVE'}}
        for key in ('OPENAI_API_KEY','TAVILY_API_KEY'):
            if not values.get(key):raise ValueError('Missing experiment credential')
            env[key]=values[key]
        env['COMPARISON_CHILD']='1'
        command=[sys.executable,'-m','experiments.adaptive_acceptance','--live','--child']
        if args.resume_batch:command+=['--resume-batch',args.resume_batch]
        if args.vacancy_pair:command+=['--vacancy-pair']
        raise SystemExit(subprocess.run(command,cwd=ROOT,env=env).returncode)
    if args.vacancy_pair:vacancy_pair()
    elif args.resume_batch:repair(args.resume_batch)
    else:execute()


def repair(batch):
    if os.environ.get('COMPARISON_CHILD')!='1' or not re.fullmatch('[a-f0-9]{32}',batch):raise ValueError('Invalid isolated batch')
    if any(('TOKEN' in k or 'KEY' in k or k.startswith('JOB_SEEKER')) and k not in {'OPENAI_API_KEY','TAVILY_API_KEY'} for k in os.environ):raise ValueError('Unexpected credentials')
    safe_home(HOME)
    target=HOME/'adaptive'/batch
    results=json.loads((target/'results.json').read_text())
    with single_worker(HOME):
        allocation=json.loads((HOME/'adaptive-allowance.json').read_text())
        current=Ledger(HOME/'budget.sqlite3','probe',.4).summary()['initial_stage_reserved_usd']
        if current+.08*len(results)>min(5,allocation['starting_reserved_usd']+allocation['additional_ceiling_usd']):raise ValueError('Repairs exceed experiment allowance')
        save(target/'results-before-resume.json',results)
        save(target/'resume-code-sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'job_seeker').glob('*.py')})
        for index,row in enumerate(results):
            root=target/row['arm'];folder=Path(row['result_path']).parent
            if row['status']=='completed':continue
            if folder.resolve().parent!= (root/'runs').resolve():raise ValueError('Invalid isolated run folder')
            ident=folder.name
            previous=Ledger(HOME/'budget.sqlite3',ident,.4).summary()['reserved_usd']
            cap=min(.4,previous+.08)
            started=time.monotonic()
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.Ledger',side_effect=lambda path,rid,limit:Ledger(HOME/'budget.sqlite3',rid,cap)):
                folder,result=run(resume=ident)
            updated={'arm':row['arm'],**metrics(folder,result,row['elapsed_s']+time.monotonic()-started),'resumed_with_fixes':True}
            results[index]=updated;save(target/'results.json',results)
            print(json.dumps({k:v for k,v in updated.items() if k not in ('budget','result_path')}),flush=True)


def vacancy_pair():
    if os.environ.get('COMPARISON_CHILD')!='1':raise ValueError('Use isolated launcher')
    if any(('TOKEN' in k or 'KEY' in k or k.startswith('JOB_SEEKER')) and k not in {'OPENAI_API_KEY','TAVILY_API_KEY'} for k in os.environ):raise ValueError('Unexpected credentials')
    safe_home(HOME)
    settings,base=load_settings()
    settings.notifications.telegram=False;settings.monitoring.enabled=False;settings.monitoring.schedule_enabled=False
    settings.review.enabled=False;settings.corroboration.enabled=False;settings.competitors.enabled=False;settings.signals.enabled=False
    settings.model.max_output_tokens=8000
    settings.limits.max_searches=6;settings.limits.max_pages=16;settings.limits.max_model_calls=18;settings.limits.run_usd=.45
    settings.adaptive.queries_per_round=2;settings.adaptive.pages_per_round=4;settings.adaptive.max_stalled_rounds=3
    with single_worker(HOME):
        allowed=json.loads((HOME/'adaptive-allowance.json').read_text())
        if Ledger(HOME/'budget.sqlite3','probe',.45).summary()['initial_stage_reserved_usd']+.9>min(5,allowed['starting_reserved_usd']+allowed['additional_ceiling_usd']):raise ValueError('Pair exceeds original allowance')
        target=HOME/'adaptive'/uuid4().hex;target.mkdir()
        save(target/'manifest.json',{'purpose':'Larger equal-budget vacancy check','settings':settings.model_dump(),'maximum_reserved_usd':.9,
             'code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'job_seeker').glob('*.py')}})
        print('Vacancy pair artifacts: '+str(target),flush=True)
        results=[]
        for arm in ['adaptive_vacancy','fixed_vacancy']:
            root=target/arm;root.mkdir();cfg=settings.model_copy(deep=True);cfg.adaptive.enabled=arm.startswith('adaptive')
            for name in [cfg.prompts.master_file,cfg.prompts.profile_file,cfg.prompts.resume_file]:
                if (base/name).exists():
                    dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((base/name).read_bytes())
            started=time.monotonic()
            with patch('job_seeker.runner.ROOT',root),patch('job_seeker.runner.load_settings',return_value=(cfg,root)),patch('job_seeker.runner.Ledger',side_effect=lambda path,ident,cap:Ledger(HOME/'budget.sqlite3',ident,cap)):
                folder,result=run()
            row={'arm':arm,**metrics(folder,result,time.monotonic()-started)};results.append(row);save(target/'results.json',results)
            print(json.dumps({k:v for k,v in row.items() if k not in ('budget','result_path')}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Acceptance stopped: '+type(exc).__name__,flush=True)
        raise SystemExit(1)
