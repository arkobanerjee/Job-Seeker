"""Private, durable API receipts and deterministic search attribution. No model calls."""
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import csv
import hashlib
import io
import json
import os
import time

ACTIVE=ContextVar('research_audit',default=None)

@contextmanager
def session():
    token=ACTIVE.set(None)
    try:yield
    finally:ACTIVE.reset(token)

def bind(state):
    state.setdefault('api_log',[])
    state.setdefault('search_log',[])
    file=Path(state.get('folder',''))/'evaluation.json'
    if state.get('folder') and file.exists():
        saved=json.loads(file.read_text(encoding='utf-8'))
        if saved.get('run_id')==state.get('run_id'):
            # A completion receipt can be newer than the last research checkpoint.
            calls={r['id']:r for r in state['api_log']}
            for row in saved.get('calls',[]):
                previous=calls.get(row['id'])
                if previous is None or row.get('finished_at','')>previous.get('finished_at',''):calls[row['id']]=row
            state['api_log']=list(calls.values())
            searches={r['id']:r for r in state['search_log']}
            for row in saved.get('searches',[]):searches.setdefault(row['id'],row)
            state['search_log']=[calls.get(ident,row) for ident,row in searches.items()]
    ACTIVE.set(state)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def save(state):
    if not state.get('folder'):return
    folder=Path(state['folder']);folder.mkdir(parents=True,exist_ok=True)
    # Atomic replacement leaves either the previous complete receipt file or the new one.
    target=folder/'evaluation.json';temporary=folder/'evaluation.json.tmp'
    temporary.write_text(json.dumps(snapshot(state),ensure_ascii=False,indent=2),encoding='utf-8')
    # Windows indexers can briefly hold a file without delete sharing.
    for attempt in range(4):
        try:os.replace(temporary,target);break
        except PermissionError:
            if attempt==3:raise
            time.sleep(.02*(attempt+1))

def start(state,provider,purpose,**fields):
    if state is None:return None
    row={'id':uuid4().hex,'provider':provider,'purpose':purpose,
         'started_at':datetime.now(timezone.utc).isoformat(),'status':'started',
         'round':state.get('rounds',0),**fields}
    state.setdefault('api_log',[]).append(row);save(state)
    return row

def finish(state,row,status,**fields):
    if row is None:return
    row.update(status=status,finished_at=datetime.now(timezone.utc).isoformat(),**fields)
    save(state)

def model_purpose(schema):
    return {'ResearchDecision':'planning','PreferenceCheck':'clarification_preflight',
            'Assessment':'page_assessment','Review':'independent_review',
            'CorroborationReview':'corroboration'}.get(schema,'model_assessment')

def search_context(state,query):
    if not state:return {}
    active=state.get('active_round',{});decision=active.get('decision',{})
    notes=next((n for n in decision.get('query_notes',[]) if n.get('query')==query),{})
    prior={s['id']:s for s in state.get('search_log',[])}
    parent=notes.get('parent_search_id') or None
    return {'origin':'adaptive' if active else 'configured',
            'plan_explanation':decision.get('explanation','') if active else 'Execute configured query',
            'parent_search_id':parent if parent in prior else None,
            'parent_reference_valid':parent in prior if parent else None,
            'change_reason':notes.get('change_reason',''),
            'expected_improvement':notes.get('expected_improvement',''),
            'target_country':notes.get('target_country','unknown'),
            'strategy':notes.get('strategy','unknown'),
            'track':next((q.get('track') for q in [*active.get('actions',{}).get('queries',[]),*state.get('config',{}).get('search',{}).get('queries',[])] if q.get('query')==query),None)}

def search_start(state,query):
    row=start(state,'tavily','search',query=query,search_depth='basic',max_results=5,**search_context(state,query))
    if row is not None:
        # One object is shared in memory; JSON snapshots intentionally retain both views.
        state['search_log'].append(row);save(state)
    return row

def canonical(url):
    from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
    try:
        p=urlsplit(url)
        query=urlencode(sorted((k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('gclid','fbclid')))
        return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/'),query,''))
    except ValueError:return str(url)

def reachable(roots,sources):
    seen=set();pending=list(roots)
    while pending and len(seen)<2000:
        url=pending.pop()
        if url in seen:continue
        seen.add(url);page=sources.get(url,{})
        pending.extend(x for x in [*page.get('links',[]),page.get('final_url'),page.get('redirect')] if x and x not in seen)
    return seen

def snapshot(state):
    sources=state.get('sources',{});done=set(state.get('pages_done',[]))
    searches=[];seen_results=set();seen_findings=set();seen_companies=set()
    for original in state.get('search_log',[]):
        row=dict(original);results=row.get('results',[])
        roots=[r['url'] for r in results if r.get('accepted',True) and r.get('url')]
        paths=reachable(roots,sources)
        findings={canonical(f.get('url',''))+'|'+f.get('title','').casefold():f for f in state.get('findings',[]) if f.get('url') in paths}
        vacancies={k:v for k,v in findings.items() if v.get('kind')=='vacancy'}
        companies={s['company'].strip().casefold() for s in state.get('signals',[]) if s.get('url') in paths and s.get('qualification_status')=='qualified'}
        urlkeys={canonical(u) for u in roots}
        fetched=paths & set(sources)
        linked_models=[c for c in state.get('api_log',[]) if c.get('provider') in ('openai','anthropic') and c.get('url') in paths]
        row['linked_model_call_ids']=[c['id'] for c in linked_models]
        row['metrics']={'returned_results':len(results),'accepted_results':len(roots),
            'new_result_urls':len(urlkeys-seen_results),'overlapping_result_urls':len(urlkeys&seen_results),
            'fetched_pages':len(fetched),'available_pages':sum(sources[u].get('http_status')==200 for u in fetched),
            'unavailable_pages':sum(sources[u].get('http_status')!=200 for u in fetched),
            'assessed_or_processed_pages':len(fetched&done),
            'linked_model_calls':len(linked_models),
            'linked_model_estimate_usd':sum(c.get('observed_estimate_usd') or 0 for c in linked_models),
            'linked_model_unknown_cost_calls':sum(c.get('observed_estimate_usd') is None for c in linked_models),
            'unread_result_urls':sum(u not in done for u in roots),
            'vacancies':len(vacancies),'excluded':sum(f.get('kind')=='excluded' for f in findings.values()),
            'rejected_proposals':sum(f.get('url') in paths for f in state.get('rejected_findings',[])),
            'additional_vacancies':len(set(vacancies)-seen_findings),
            'qualified_companies':len(companies),'additional_qualified_companies':len(companies-seen_companies)}
        # Cache/rejected attempts never acquire discovery credit.
        if row.get('status')=='success':
            seen_results.update(urlkeys);seen_findings.update(vacancies);seen_companies.update(companies)
        else:
            row['metrics']['additional_vacancies']=0;row['metrics']['additional_qualified_companies']=0
        searches.append(row)
    calls=state.get('api_log',[]);groups={}
    for call in calls:
        key=call['provider']+':'+call['purpose']
        group=groups.setdefault(key,{'attempts':0,'success':0,'failed_or_unresolved':0,'observed_estimate_usd':0.,'cost_unknown_calls':0,'duration_ms':0})
        group['attempts']+=1;group['success']+=call['status'] in ('success','cached')
        group['failed_or_unresolved']+=call['status'] in ('failed','started','output_limit','invalid_output','interrupted','uncertain','unavailable')
        cost=call.get('observed_estimate_usd')
        if cost is not None:group['observed_estimate_usd']+=cost
        elif call.get('provider') in ('openai','anthropic','tavily'):group['cost_unknown_calls']+=1
        group['duration_ms']+=call.get('duration_ms',0)
    return {'schema_version':1,'run_id':state.get('run_id'),'operation':state.get('mode','unknown'),
        'fingerprint':state.get('fingerprint'),'status':state.get('status'),
        'attribution_available':'findings' in state and 'sources' in state,
        'rejected_proposals':state.get('rejected_findings',[]),
        'findings':[dict({k:f.get(k) for k in ('url','title','company','kind','fit','review_status','independent_review')},
                         catalog_id=hashlib.sha256((f.get('url','')+'\n'+f.get('title','').casefold()).encode()).hexdigest()[:24]) for f in state.get('findings',[])],
        'stop_reason':state.get('stop_reason'),'searches':searches,'calls':calls,'by_purpose':groups,
        'review_effects':[e for e in state.get('research_trace',[]) if e.get('type')=='review_effect'],
        'plans':[{'round':e.get('round'),'decision':e.get('decision'),'admitted':e.get('admitted')} for e in state.get('research_trace',[]) if e.get('type')=='plan'],
        'note':'Attribution uses observed links and first successful search order; it is not causal improvement or human-labelled precision. Unread results remain unevaluated. Started receipts have uncertain outcomes. Costs are estimates, not invoices. Prompts, candidate answers and request credentials are omitted.'}

def csv_report(report):
    stream=io.StringIO();fields=['id','query','parent_search_id','change_reason','expected_improvement','target_country','strategy','status','observed_estimate_usd','returned_results','new_result_urls','overlapping_result_urls','fetched_pages','unread_result_urls','vacancies','additional_vacancies','qualified_companies','additional_qualified_companies']
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    for row in report.get('searches',[]):
        values={k:row.get(k,row.get('metrics',{}).get(k,'')) for k in fields}
        # Spreadsheet applications must not interpret model/source strings as formulae.
        values={k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for k,v in values.items()}
        writer.writerow(values)
    return stream.getvalue()
