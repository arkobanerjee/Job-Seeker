"""Separate A/B harness. Default mode is deterministic, offline and free."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4

from job_seeker.budget import Ledger, BudgetExceeded
from job_seeker.research import Report, validate_findings
from job_seeker.reviewer import Review, apply_review
from job_seeker.runner import Assessment, POLICY, invoke_model, single_worker
from job_seeker.settings import ROOT, Settings, render_prompt
from job_seeker.sources import SourceTools

HOME = ROOT / 'private/comparison'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Trace:
    def __init__(self, folder, metadata):
        self.folder, self.metadata = folder, metadata
        self.lock = threading.Lock()
        self.context = threading.local()

    def emit(self, event, **fields):
        row = dict(self.metadata, timestamp=datetime.now(timezone.utc).isoformat(),
                   event_type=event, **fields)
        with self.lock:
            with (self.folder / 'trace.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')

    @contextmanager
    def action(self, kind, worker, task, parent=None, **parameters):
        ident = uuid4().hex
        start = time.monotonic()
        common = dict(event_id=ident, worker_id=worker, task_id=task, parent_event_id=parent)
        self.emit(kind + '_start', **common, parameters=parameters)
        previous = getattr(self.context, 'event', None)
        self.context.event = ident
        try:
            yield ident
        except Exception as exc:
            self.emit(kind + '_failure', **common, duration_s=time.monotonic()-start,
                      error_type=type(exc).__name__)
            raise
        else:
            self.emit(kind + '_complete', **common, duration_s=time.monotonic()-start)
        finally:
            self.context.event = previous

    def artifact(self, ident, value):
        save(self.folder / 'artifacts' / (ident + '.json'), value)
        self.emit('artifact', parent_event_id=ident, reference='artifacts/'+ident+'.json', sha256=digest(value))


class FrozenTools:
    """Query-aware finite search corpus; labels are never returned to assessors."""
    def __init__(self, corpus):
        self.corpus = corpus

    def search(self, query):
        return [dict(url=x['url'], title=x['title']) for x in self.corpus['pages']
                if any(word.casefold() in query.casefold() for word in x['search_terms'])]

    def fetch(self, url):
        item = next(x for x in self.corpus['pages'] if x['url']==url)
        if item.get('simulate_failure'):
            return {'url':url, 'error':'Simulated retrieval failure'}
        return {key:item[key] for key in ('url','title','source_id','text','http_status','observed_at')}

    def assess(self, page, track):
        # Fixed stand-in tests plumbing only; never claims to measure model quality.
        from job_seeker.research import Finding
        if page.get('http_status')!=200:
            return Assessment()
        return Assessment(source_type='employer', findings=[Finding(
            kind='vacancy', track=track, company='Example employer', title=page['title'],
            url=page['url'], source_id=page['source_id'], evidence_quote=page['text'],
            fit='possible', fit_reason='Synthetic harness fixture', language='unknown',
            language_status='unknown', location='Germany', eligibility='unknown',
            eligibility_status='unknown', concerns=[])])

    def review(self, finding, page):
        return Review(verdict='manual_review', reason='Synthetic review; no eligibility inference')


class TracedLedger:
    def __init__(self, ledger, trace):
        self.ledger, self.trace = ledger, trace

    def reserve(self, kind, amount):
        ident=self.ledger.reserve(kind,amount)
        self.trace.emit('reservation',parent_event_id=getattr(self.trace.context,'event',None),
                        reservation_id=ident,kind=kind,reserved_usd=amount)
        return ident

    def observe(self, ident, usd):
        self.ledger.observe(ident,usd)
        self.trace.emit('usage',parent_event_id=getattr(self.trace.context,'event',None),
                        reservation_id=ident,observed_estimate_usd=usd)

    def summary(self):
        return self.ledger.summary()


class LiveTools:
    def __init__(self, settings, prompt, ledger, folder):
        self.settings, self.prompt, self.ledger = settings, prompt, ledger
        folder.mkdir(parents=True, exist_ok=True)
        self.state = dict(model_calls=0, folder=str(folder), usage=[],run_id=folder.name,mode='comparison',api_log=[],search_log=[])
        def persist():
            from job_seeker.telemetry import save as save_evaluation
            self.state.update(sources=self.tools.records,cache=self.tools.cache)
            save_evaluation(self.state)
        self.tools = SourceTools(ledger, persist, max_searches=1, max_fetches=settings.limits.max_pages)
        self.tools.audit_state=self.state

    def search(self, query):
        return self.tools.search(query)

    def fetch(self, url):
        return self.tools.fetch(url)

    def assess(self, page, track):
        # Preserve the complete source artifact, but avoid unbounded structured ATS
        # metadata/link arrays in model context. Evidence checks use the original.
        compact={key:page[key] for key in ('url','source_id','http_status','text','posting_title',
                                          'closed_marker','closed_marker_quote') if key in page}
        compact['links']=[link for link in sorted(page.get('links',[]),key=link_priority,reverse=True)[:10] if len(link)<=500]
        return self._invoke(self.prompt+'\n'+POLICY+'\nTRACK: '+track+
                            '\nSOURCE:\n'+json.dumps(compact,ensure_ascii=False), Assessment)

    def _invoke(self, prompt, schema):
        previous=len(self.state['usage'])
        result=invoke_model(self.settings,prompt,self.ledger,self.state,schema=schema)
        save(Path(self.state['folder'])/'checkpoint.json',self.state)
        for usage in self.state['usage'][previous:]:
            self.ledger.trace.emit('model_tokens',parent_event_id=getattr(self.ledger.trace.context,'event',None),
                                   usage=usage)
        return result

    def review(self, finding, page):
        compact={key:page[key] for key in ('url','source_id','http_status','text','posting_title',
                                          'closed_marker','closed_marker_quote') if key in page}
        return self._invoke(self.prompt+'\n'+POLICY+
                            '\nIndependently review this proposed finding against the supplied page. '
                            'Reject only with exact blocker quotes. Otherwise accept or retain for manual review.\n'+
                            json.dumps({'finding':finding,'page':compact},ensure_ascii=False), Review)


def link_priority(url):
    """Rank actual observed URLs; never synthesize a vacancy link."""
    p=urlsplit(url);path=p.path.lower()
    score=sum(token in path for token in ('/job/','/jobs/','/positions/','/careers/','/vacancies/'))*3
    score+=2*any(host in p.hostname for host in ('greenhouse.io','lever.co','personio','recruitee')) if p.hostname else 0
    score-=10*any(token in path for token in ('/login','/privacy','/terms','/signup','/blog/','/search'))
    return score


class Coverage:
    """Bounded deterministic coordination, no additional model planner."""
    def __init__(self):
        self.lock=threading.Lock();self.claims={}

    def claim(self,url,worker):
        from job_seeker.sources import normalized
        key=normalized(url)
        with self.lock:
            owner=self.claims.get(key)
            if owner:return False,owner
            self.claims[key]=worker
            return True,worker


def task_run(task, worker, backend, trace, coverage=None, max_pages=2):
    findings, records, questions = [], {}, []
    with trace.action('task', worker, task['id']) as task_event:
        try:
            with trace.action('search', worker, task['id'], task_event, query=task['query']) as event:
                results = backend.search(task['query'])
                trace.artifact(event, results)
            if not isinstance(results, list):
                raise ValueError('Search returned no result list')
            queue = [(x['url'], event) for x in sorted(results,key=lambda x:link_priority(x['url']),reverse=True)]
            visited = set()
            while queue and len(visited)<max_pages:
                url, parent = queue.pop(0)
                if url in visited:
                    continue
                if coverage:
                    with trace.action('coordination',worker,task['id'],parent,url=url) as coord:
                        claimed,owner=coverage.claim(url,worker)
                        trace.emit('coverage_claim' if claimed else 'coverage_skip',parent_event_id=coord,
                                   url=url,worker_id=worker,owner=owner)
                    if not claimed:continue
                visited.add(url)
                with trace.action('fetch', worker, task['id'], parent, url=url) as fetch_event:
                    page = backend.fetch(url)
                    trace.artifact(fetch_event, page)
                records[url] = page
                if page.get('http_status')!=200:
                    trace.emit('source_unavailable', parent_event_id=fetch_event, url=url)
                    continue
                with trace.action('assessment', worker, task['id'], fetch_event, url=url) as assess_event:
                    assessment = backend.assess(page, task['track'])
                    trace.artifact(assess_event, assessment.model_dump())
                if assessment.clarification:
                    questions.append({'question':assessment.clarification, 'reason':assessment.clarification_reason})
                good, bad = validate_findings(Report(findings=[] if assessment.source_type=='index'
                                                  else assessment.findings, limitations=[]), {url:page})
                for item in good:
                    item['discovered_by'] = worker
                    item['assessment_event_id'] = assess_event
                    findings.append(item)
                trace.emit('validation', parent_event_id=assess_event, accepted=len(good), rejected=len(bad))
                follow=[link for link in assessment.follow_links if link in page.get('links',[])]
                if assessment.source_type=='index':
                    follow.extend(link for link in sorted(page.get('links',[]),key=link_priority,reverse=True)
                                  if link_priority(link)>=3 and link not in follow)
                # Prefer promising observed follow-up links over remaining search indexes.
                queue[0:0]=[(link, assess_event) for link in dict.fromkeys(follow)]
        except Exception as exc:
            trace.emit('task_stopped', worker_id=worker, task_id=task['id'], error_type=type(exc).__name__)
            return dict(status='failed', error_type=type(exc).__name__, findings=findings, records=records, questions=questions)
    return dict(status='completed', findings=findings, records=records, questions=questions)


def run_arm(home, batch, arm, tasks, factory, cap=.30, live=False, max_pages=2):
    ident = uuid4().hex
    folder = home / 'results' / batch / (arm+'-'+ident)
    folder.mkdir(parents=True)
    ledger = Ledger(home/'budget.sqlite3', ident, cap) if live else None
    trace = Trace(folder, {'run_id':ident,'arm':arm,'batch_id':batch,'mode':'live' if live else 'simulation'})
    if ledger:
        ledger=TracedLedger(ledger,trace)
    start = time.monotonic()
    coverage=Coverage() if arm=='C' else None
    def work(index, task):
        worker = 'worker-1' if arm=='A' else 'worker-'+str(index+1)
        return task_run(task, worker, factory(ledger, folder / ('task-'+str(index))), trace,coverage,max_pages)
    if arm=='A':
        parts = [work(i,t) for i,t in enumerate(tasks)]
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(work,i,t) for i,t in enumerate(tasks)]
            parts = [f.result() for f in futures]
    records = {url:page for part in parts for url,page in part['records'].items()}
    unique = {}
    for part in parts:
        for finding in part['findings']:
            key = (finding['url'],finding['title'].casefold())
            if key in unique:
                trace.emit('deduplicated', url=finding['url'], duplicate_event=finding['assessment_event_id'],
                           retained_event=unique[key]['assessment_event_id'])
            else:
                unique[key] = finding
    reviewer = factory(ledger,folder/'reviewer')
    review_failures = 0
    for finding in sorted(unique.values(),key=lambda f:(f['url'],f['title']))[:2]:
        try:
            with trace.action('review','reviewer','final',finding['assessment_event_id'],url=finding['url']) as event:
                review = reviewer.review(finding,records[finding['url']])
                trace.artifact(event,review.model_dump())
                finding.update(apply_review(finding,review,records[finding['url']]))
        except Exception as exc:
            review_failures += 1
            finding['review_error_type']=type(exc).__name__
    result = dict(run_id=ident, arm=arm, mode='live' if live else 'simulation',
                  status='completed' if all(p['status']=='completed' for p in parts) and not review_failures else 'partial',
                  elapsed_s=time.monotonic()-start, findings=list(unique.values()),
                  questions=[q for p in parts for q in p['questions']], task_statuses=[p['status'] for p in parts],
                  budget=ledger.summary() if live else {'reserved_usd':0,'observed_estimate_usd':0},
                  limitations=['Simulation measures harness behavior, not model quality or live search performance.'] if not live
                  else ['Fixed bounded subtasks; no dynamic planner. Maximum two findings independently reviewed.',
                        'Observed estimates are not invoices; retained reservations govern the cap.'])
    save(folder/'result.json',result)
    events=[json.loads(line) for line in (folder/'trace.jsonl').read_text(encoding='utf-8').splitlines()]
    counts={kind:sum(e['event_type']==kind for e in events) for kind in
            ('search_start','fetch_start','assessment_start','review_start','source_unavailable','deduplicated','task_stopped','coordination_start','coverage_skip')}
    result['process_counts']=counts
    result['unique_fetched_urls']=len(records)
    result['quality_status']='requires_blind_labels'
    save(folder/'result.json',result)
    return result


def safe_home(home):
    home = Path(home).resolve()
    if home != HOME.resolve():
        raise ValueError('Experiment workspace must be private/comparison')
    if any(path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction())
           for path in [home,*home.parents] if path.exists()):
        raise ValueError('Linked experiment workspace is forbidden')
    # Refuse linked existing child paths before writing any experiment output.
    if home.exists() and any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in home.rglob('*')):
        raise ValueError('Linked experiment files are forbidden')
    return home


def execute(home=HOME, live=False, arms=None, tasks_override=None, order_override=None, max_pages=2):
    if live and os.environ.get('COMPARISON_CHILD')!='1':
        raise ValueError('Live calls require the credential-isolated launcher')
    home = safe_home(home)
    config = json.loads((home/'experiment.json').read_text(encoding='utf-8'))
    arm_cap=float(config.get('per_arm_usd',.30))
    if not 0<arm_cap<=.30:raise ValueError('Pilot arm allowance must be at most $0.30')
    arms=arms or ['A','B']
    if not arms or len(set(arms))!=len(arms) or set(arms)-{'A','B','C'}:raise ValueError('Invalid comparison arms')
    if config['total_budget_usd']!=5 or config['production_state_access'] or config['production_budget_access']:
        raise ValueError('Unsupported experiment policy')
    model={'provider':config['model_provider'],'name':config['model'],
           'input_usd_per_million':config.get('input_usd_per_million',.20),
           'output_usd_per_million':config.get('output_usd_per_million',1.20)}
    if model['name']=='gpt-6-luna' and (model['input_usd_per_million']<.10 or model['output_usd_per_million']<.50):
        raise ValueError('Rates below verified GPT-6 Luna standard pricing')
    settings = Settings(model=model,
                        search={'queries':[{'track':'ai','query':'AI Engineer RAG Germany English'}]})
    settings.prompts.master_file='master.md';settings.prompts.profile_file='profile.md';settings.prompts.resume_file='resume.md'
    prompt = render_prompt(settings,home)
    corpus = json.loads((Path(__file__).parent/'fixtures/corpus.json').read_text())
    tasks = tasks_override or corpus['tasks']
    if len(tasks)!=2 or not 1<=max_pages<=4:raise ValueError('Exactly two bounded subtasks required')
    settings.limits.max_pages=max_pages
    if live:
        if os.environ.get('COMPARISON_CHILD')!='1':
            raise ValueError('Live calls require the credential-isolated launcher')
        allowed = {'OPENAI_API_KEY','ANTHROPIC_API_KEY','TAVILY_API_KEY'}
        if any(('TOKEN' in key or 'KEY' in key or key.startswith('JOB_SEEKER')) and key not in allowed for key in os.environ):
            raise ValueError('Unexpected credentials in comparison process')
        settings.limits.max_model_calls=max_pages+2
        per_call=((settings.limits.context_bytes+8000)*settings.model.input_usd_per_million+
                  settings.model.max_output_tokens*settings.model.output_usd_per_million)/1e6
        if 2*.008+(2*max_pages+2)*per_call>arm_cap:
            raise BudgetExceeded('Worst-case pilot calls exceed per-arm envelope')
        factory = lambda ledger,folder:LiveTools(settings,prompt,ledger,folder)
    else:
        factory = lambda ledger,folder:FrozenTools(corpus)
    with single_worker(home):
        if live:
            probe = Ledger(home/'budget.sqlite3','preflight',.30)
            if probe.summary()['initial_stage_reserved_usd']+len(arms)*arm_cap>5:
                raise BudgetExceeded('Complete A/B pair does not fit remaining experiment allowance')
        batch = uuid4().hex
        target = home/'results'/batch
        target.mkdir(parents=True)
        save(target/'inputs.json',{'config':config,'settings':settings.model_dump(), 'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
                                 'corpus_sha256':digest(corpus),'tasks':tasks})
        (target/'prompt.md').write_text(prompt,encoding='utf-8')
        # Alternate order between batches; the randomized order is preserved.
        order = order_override or (arms if int(batch[-1],16)%2==0 else list(reversed(arms)))
        if sorted(order)!=sorted(arms):raise ValueError('Invalid arm order')
        results = [run_arm(home,batch,arm,tasks,factory,cap=arm_cap,live=live,max_pages=max_pages) for arm in order]
        save(target/'comparison.json',results)
        rows = [dict(arm=r['arm'],mode=r['mode'],status=r['status'],elapsed_s=r['elapsed_s'],
                     unique_findings=len(r['findings']),reserved_usd=r['budget']['reserved_usd'],
                     observed_estimate_usd=r['budget']['observed_estimate_usd']) for r in results]
        with (target/'comparison.csv').open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        save(target/'review-labels.json',{'instructions':'Label pooled jobs without opening arm results. No automatic quality scores.',
             'items':[{'url':url,'title':title,'relevant':None,'barriers_correct':None}
                      for url,title in sorted({(f['url'],f['title']) for r in results for f in r['findings']})]})
        lines=['# Comparison pilot report', '',
               'Mode: '+('live' if live else 'offline simulation; timings and findings do not measure real agent performance'),'',
               '| Arm | Status | Seconds | Findings before human labels | Searches | Fetches | Unavailable | Duplicate findings | Reserved USD |',
               '|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for result in sorted(results,key=lambda r:r['arm']):
            counts=result['process_counts']
            lines.append(f"| {result['arm']} | {result['status']} | {result['elapsed_s']:.3f} | {len(result['findings'])} | {counts['search_start']} | {counts['fetch_start']} | {counts['source_unavailable']} | {counts['deduplicated']} | {result['budget']['reserved_usd']:.4f} |")
        sets=[{(f['url'],f['title'].casefold()) for f in r['findings']} for r in results]
        overlap=len(set.intersection(*sets))/len(set.union(*sets)) if set.union(*sets) else None
        lines.extend(['', 'Final finding-set overlap (intersection / union): '+str(overlap), '',
                      'Precision, recall, useful yield and cost per useful job await human labels. '+
                      'Source failures remain failures; they do not imply closed jobs. '+
                      'This small fixed-task pilot cannot establish which architecture is better.', '',
                      'Artifacts: comparison.json, comparison.csv, review-labels.json; each arm has trace.jsonl and source/assessment/review artifacts.'])
        (target/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly execute one paid A/B pair within separate $5 gate')
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--suite',action='store_true',help='Run all three configurations across three briefs and two repeats')
    args=parser.parse_args()
    if args.live and not args.child:
        from dotenv import dotenv_values
        values=dotenv_values(ROOT/'.env')
        config=json.loads((HOME/'experiment.json').read_text())
        key='OPENAI_API_KEY' if config['model_provider']=='openai' else 'ANTHROPIC_API_KEY'
        env={k:v for k,v in os.environ.items() if k.upper() in
             {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','COMSPEC','PATHEXT','SYSTEMDRIVE'}}
        for name in (key,'TAVILY_API_KEY'):
            value=values.get(name) or os.environ.get(name)
            if not value:raise ValueError('Missing experiment provider credential')
            env[name]=value
        env['COMPARISON_CHILD']='1'
        completed=subprocess.run([sys.executable,'-m','experiments.comparison','--live','--child']+(['--suite'] if args.suite else []),cwd=ROOT,env=env)
        raise SystemExit(completed.returncode)
    if args.child and not args.live:raise ValueError('Invalid child mode')
    if args.suite:
        from .suite import run
        run(live=args.live)
    else:
        print('Comparison saved: '+str(execute(live=args.live)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Comparison stopped: '+type(exc).__name__)
        raise SystemExit(1)
