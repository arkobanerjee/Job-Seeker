"""Three configurations, three briefs, two repeats; separate experiment budget."""
import json
from pathlib import Path
import statistics
from uuid import uuid4
from . import comparison as c

BRIEFS=[
    {'id':'germany-ai','tasks':[
        {'id':'rag','track':'ai','query':'Germany AI Engineer RAG LLM English (site:jobs.lever.co OR site:job-boards.greenhouse.io)'},
        {'id':'applied-ai','track':'ai','query':'Germany Applied AI Engineer machine learning English (site:jobs.personio.de OR site:recruitee.com)'}]},
    {'id':'germany-data','tasks':[
        {'id':'data-science','track':'data','query':'Germany Data Scientist XGBoost Python English (site:jobs.lever.co OR site:job-boards.greenhouse.io)'},
        {'id':'analytics','track':'data','query':'Germany Data Analyst Analytics Engineer SQL English (site:jobs.personio.de OR site:recruitee.com)'}]},
    {'id':'international','tasks':[
        {'id':'ai-international','track':'ai','query':'Europe UAE remote AI Engineer RAG English (site:jobs.lever.co OR site:job-boards.greenhouse.io)'},
        {'id':'data-international','track':'data','query':'Europe UAE remote Data Scientist Analyst English (site:jobs.lever.co OR site:job-boards.greenhouse.io)'}]},
]


def summarize(folder, entries):
    rows=[]
    for entry in entries:
        for result in json.loads((Path(entry['folder'])/'comparison.json').read_text(encoding='utf-8')):
            rows.append(dict(result,brief=entry['brief'],repeat=entry['repeat']))
    c.save(folder/'all-runs.json',rows)
    lines=['# Three-configuration comparison', '',
           'A: one sequential researcher. B: two independent parallel researchers. C: two parallel researchers sharing atomic URL coverage claims.',
           'C uses deterministic coordination, not an extra model supervisor. All arms share identical task limits and final review rules.', '',
           '| Arm | Runs | Completed | Mean seconds | Min-max seconds | Candidate vacancy records* | Excluded/reference records | Search calls | Fetch calls | Coverage skips | Reserved USD | Observed estimate USD |',
           '|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm in 'ABC':
        group=[r for r in rows if r['arm']==arm]
        if not group:continue
        durations=[r['elapsed_s'] for r in group]
        lines.append(f"| {arm} | {len(group)} | {sum(r['status']=='completed' for r in group)} | {statistics.mean(durations):.2f} | {min(durations):.2f}-{max(durations):.2f} | "
                     f"{sum(f['kind']=='vacancy' for r in group for f in r['findings'])} | {sum(f['kind']=='excluded' for r in group for f in r['findings'])} | "
                     f"{sum(r['process_counts']['search_start'] for r in group)} | {sum(r['process_counts']['fetch_start'] for r in group)} | "
                     f"{sum(r['process_counts']['coverage_skip'] for r in group)} | {sum(r['budget']['reserved_usd'] for r in group):.4f} | {sum(r['budget']['observed_estimate_usd'] for r in group):.6f} |")
    lines.extend(['', '*Candidate vacancy records are model/evidence-checked outputs, not human-labelled useful jobs or independently confirmed availability. Counts sum runs and can repeat the same job.', '',
                  '## Paired timings', '', '| Brief | Repeat | A seconds | B seconds | C seconds |', '|---|---:|---:|---:|---:|'])
    for entry in entries:
        values={r['arm']:r['elapsed_s'] for r in rows if r['brief']==entry['brief'] and r['repeat']==entry['repeat']}
        lines.append(f"| {entry['brief']} | {entry['repeat']} | {values['A']:.2f} | {values['B']:.2f} | {values['C']:.2f} |")
    lines.extend(['', 'All runs, including partial failures, are retained. Six paired trials are exploratory; network variation, changing search results and a small workload limit generalization. No statistical significance is claimed.', '',
                  'Each trial directory contains source snapshots, ordered traces, model token usage, reservations and a blinded label worksheet. Quality precision/recall, useful yield and cost per useful job require independent labels. Different final reviewer coverage is visible: at most two records reviewed per run.', '',
                  'Duplicate URL ownership in C persists after a failed fetch. It can reduce repeated work but can also prevent another worker recovering that source or assessing it for a different track. Trace coverage_skip events expose this trade-off. No email, Telegram messages, applications or production writes occur.'])
    (folder/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    pooled=sorted({(f['url'],f['title']) for r in rows for f in r['findings']})
    c.save(folder/'blind-labels.json',{'items':[{'url':url,'title':title,'relevant':None,'barrier_accuracy':None} for url,title in pooled],
                                    'instructions':'Label against the frozen candidate background and captured sources without consulting arm identities.'})


def run(live=False):
    home=c.safe_home(c.HOME)
    config=json.loads((home/'experiment.json').read_text(encoding='utf-8'))
    cap=float(config.get('per_arm_usd',.2))
    if not 0<cap<=.30:raise ValueError('Invalid suite allowance')
    if live:
        if c.os.environ.get('COMPARISON_CHILD')!='1':raise ValueError('Use the isolated launcher')
        ledger=c.Ledger(home/'budget.sqlite3','suite-preflight',cap)
        if ledger.summary()['initial_stage_reserved_usd']+18*cap>5:
            raise c.BudgetExceeded('All 18 run envelopes must fit the existing $5 allowance')
    ident=uuid4().hex;folder=home/'suites'/ident;folder.mkdir(parents=True)
    c.save(folder/'manifest.json',{'suite_id':ident,'live':live,'briefs':BRIEFS,'repeats':2,
                                 'arms':['A','B','C'],'per_arm_usd':cap,'max_pages_per_task':3,
                                 'code_sha256':c.digest({name:(Path(__file__).parent/name).read_text(encoding='utf-8') for name in ('comparison.py','suite.py')}),
                                 'config':config})
    entries=[]
    for index in range(6):
        brief=BRIEFS[index//2];repeat=index%2+1
        # Each arm appears first twice, second twice and last twice.
        orders=[['A','B','C'],['B','C','A'],['C','A','B'],['A','C','B'],['C','B','A'],['B','A','C']]
        result=c.execute(live=live,arms=['A','B','C'],tasks_override=brief['tasks'],order_override=orders[index],max_pages=3)
        entries.append({'brief':brief['id'],'repeat':repeat,'folder':str(result),'order':orders[index]})
        c.save(folder/'progress.json',entries)
        summarize(folder,entries)
        print(f"Completed trial {index+1}/6: {brief['id']}, repeat {repeat}",flush=True)
    print('Suite saved: '+str(folder),flush=True)
    return folder
