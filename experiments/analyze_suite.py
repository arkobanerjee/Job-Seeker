"""Offline process audit of a completed suite; no model/search/cloud calls."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
from .comparison import HOME, safe_home, save


def analyze(folder):
    home=safe_home(HOME)
    folder=Path(folder).resolve()
    if not folder.is_relative_to(home/'suites'):raise ValueError('Private suite folder required')
    entries=json.loads((folder/'progress.json').read_text(encoding='utf-8'))
    audits=[];pairwise=[]
    for entry in entries:
        root=Path(entry['folder']).resolve()
        if not root.is_relative_to(home/'results'):raise ValueError('Invalid trial workspace')
        results=json.loads((root/'comparison.json').read_text(encoding='utf-8'))
        sets={}
        for result in results:
            arm=root/(result['arm']+'-'+result['run_id'])
            events=[json.loads(line) for line in (arm/'trace.jsonl').read_text(encoding='utf-8').splitlines()]
            types=Counter(e['event_type'] for e in events)
            fetched=[e['parameters']['url'] for e in events if e['event_type']=='fetch_start']
            queries=[e['parameters']['query'] for e in events if e['event_type']=='search_start']
            sets[result['arm']]=set(fetched)
            tokens=[e['usage'] for e in events if e['event_type']=='model_tokens']
            audits.append({'brief':entry['brief'],'repeat':entry['repeat'],'arm':result['arm'],
                'run_id':result['run_id'],'status':result['status'],'queries':queries,'fetched_urls':fetched,
                'input_tokens':sum(u.get('input_tokens',0) for u in tokens),
                'output_tokens':sum(u.get('output_tokens',0) for u in tokens),
                'coordination_seconds':sum(e['duration_s'] for e in events if e['event_type']=='coordination_complete'),
                'coverage_skips':types['coverage_skip'],
                'repeated_fetches_within_run':len(fetched)-len(set(fetched)),
                'error_types':dict(Counter(e.get('error_type','unknown') for e in events if e['event_type']=='task_stopped')),
                'verdicts':dict(Counter(f.get('independent_review',{}).get('verdict','unreviewed') for f in result['findings'])),
                'candidate_vacancies':sum(f['kind']=='vacancy' for f in result['findings']),
                'distinct_job_records':sorted({(f['url'],f['title']) for f in result['findings']})})
        for first,second in [('A','B'),('A','C'),('B','C')]:
            union=sets[first]|sets[second]
            pairwise.append({'brief':entry['brief'],'repeat':entry['repeat'],'arms':first+'/'+second,
                             'fetched_url_overlap':len(sets[first]&sets[second])/len(union) if union else None})
    save(folder/'process-audit.json',{'runs':audits,'source_overlap':pairwise})
    lines=['# Process audit', '',
           'All setups receive the same fixed queries in each trial. Differences in selected/fetched sources and outputs can arise from search-result variation, model choices and coordination. Search wording diversity is not the variable tested here.', '',
           '| Arm | Input tokens | Output tokens | Duplicate fetch attempts within runs | Coverage skips | Coordination seconds |',
           '|---|---:|---:|---:|---:|---:|']
    for arm in 'ABC':
        group=[r for r in audits if r['arm']==arm]
        lines.append(f"| {arm} | {sum(r['input_tokens'] for r in group)} | {sum(r['output_tokens'] for r in group)} | {sum(r['repeated_fetches_within_run'] for r in group)} | {sum(r['coverage_skips'] for r in group)} | {sum(r['coordination_seconds'] for r in group):.5f} |")
    lines.extend(['', '## Fetched source overlap', '', '| Trial | A/B | A/C | B/C |', '|---|---:|---:|---:|'])
    for entry in entries:
        values={r['arms']:r['fetched_url_overlap'] for r in pairwise if r['brief']==entry['brief'] and r['repeat']==entry['repeat']}
        formatted=[f"{values[key]:.2f}" if values[key] is not None else 'undefined' for key in ('A/B','A/C','B/C')]
        lines.append('| '+entry['brief']+' repeat '+str(entry['repeat'])+' | '+' | '.join(formatted)+' |')
    lines.extend(['', 'Overlap uses exact observed URLs; aliases may reduce apparent overlap. Duplicate fetches are attempts, not proof of wasted work. Coordination seconds sum local action durations, not an independently estimated causal latency penalty.', '',
                  'Full query strings, fetched URLs, token counts, task error categories and review verdict counts are saved in process-audit.json. No precision, recall or true useful-job yield is inferred from model verdicts.'])
    (folder/'process-audit.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return audits


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder')
    analyze(parser.parse_args().folder)
