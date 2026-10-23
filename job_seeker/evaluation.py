"""Score externally produced assessments against labelled frozen examples; no API calls."""
import argparse
import json
from pathlib import Path
from .research import Report,validate_findings
from .runner import Assessment
from .signals import validate_signals


def score(cases,predictions):
    ids=[x['id'] for x in cases]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate benchmark IDs')
    if set(predictions)-set(ids):raise ValueError('Unknown prediction IDs')
    rows=[];tp=fp=fn=0
    for case in cases:
        expected=case['expected'];item=predictions.get(case['id'])
        if item is None:
            rows.append({'id':case['id'],'passed':False,'errors':['missing_prediction']})
            fn+=int(expected['kind']=='vacancy');continue
        assessment=Assessment.model_validate(item)
        findings=[] if assessment.source_type=='index' else assessment.findings
        good,bad=validate_findings(Report(findings=findings,limitations=[]),{case['source']['url']:case['source']})
        signals,_=validate_signals(assessment.signals,case['source'],'evaluation')
        # One labelled target per case. Extra outputs count as a failure, not a lucky match.
        category=good[0]['kind'] if len(good)==1 else 'signal' if not good and signals else 'unverified' if not good else 'multiple'
        errors=[]
        if category!=expected['kind']:errors.append('category')
        if good and any(f['title'].casefold()!=case['title'].casefold() for f in good):errors.append('target_title')
        for field in expected.get('unknown_fields',[]):
            if good and any(f.get(field,'').strip().casefold()!='unknown' for f in good):errors.append('unsupported_'+field)
            if expected.get('require_fact_status') and good and any(f.get(field+'_status')!='unknown' for f in good):errors.append('missing_'+field+'_status')
        if expected.get('requires_rejection_reason') and good:
            if not assessment.rejection_reasons and not any(f.get('mandatory_conflicts') for f in good):errors.append('missing_rejection_reason')
        predicted=any(f['kind']=='vacancy' for f in good)
        relevant=expected['kind']=='vacancy'
        tp+=int(predicted and relevant);fp+=int(predicted and not relevant);fn+=int(relevant and not predicted)
        rows.append({'id':case['id'],'passed':not errors,'errors':errors,'category':category,'unverified_outputs':len(bad)})
    return {'cases':len(cases),'submitted':sum(x in predictions for x in ids),
            'passed':sum(x['passed'] for x in rows),'shortlist_precision':tp/(tp+fp) if tp+fp else None,
            'shortlist_recall':tp/(tp+fn) if tp+fn else None,'false_shortlists':fp,'missed_shortlists':fn,
            'contract_version':2,'results':rows,'scope':'Frozen examples only; not search coverage, legal eligibility or live job availability.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','score'])
    parser.add_argument('--cases',type=Path,default=Path(__file__).resolve().parent.parent/'tests/fixtures/quality_cases.json')
    parser.add_argument('--predictions',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();cases=json.loads(args.cases.read_text(encoding='utf-8'))
    if args.command=='prepare':
        result={'instructions':'Produce an Assessment JSON object per ID against this profile. Do not invent facts. Return unknown for unstated language or eligibility.',
                'profile':'One year AI/RAG deployment; four years data/analytics, overlap unknown. Basic German, native English. Indian citizen with German job seeker visa; no other stated work rights.',
                'cases':[{k:v for k,v in case.items() if k!='expected'} for case in cases]}
    else:
        if not args.predictions:parser.error('score requires --predictions')
        result=score(cases,json.loads(args.predictions.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Wrote evaluation '+args.command+' output')
    if args.command=='score' and result['passed']!=result['cases']:raise SystemExit(1)


if __name__=='__main__':main()
