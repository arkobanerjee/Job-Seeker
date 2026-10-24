"""Timestamped action receipts and bounded, allowlisted dashboard summaries."""
import json
from datetime import datetime,timezone


def record(state,kind,**fields):
    state.setdefault('research_trace',[]).append({'at':datetime.now(timezone.utc).isoformat(),'type':kind,**fields})


def trace_summary(state,max_bytes=16000):
    raw=state.get('research_trace',[])
    events=[]
    scalar=('query','url','from_url','reason','error','error_type','http_status','round','inspected','new_records',
            'result_count','call','model','effort','input_tokens','output_tokens','observed_estimate_usd','reused','outcome')
    for index,item in enumerate(raw):
        row={'sequence':index+1,'at':str(item.get('at',''))[:60],'type':str(item.get('type','unknown'))[:40]}
        for key in scalar:
            if key in item:
                value=item[key]
                row[key]=value if value is None or isinstance(value,(int,float,bool)) else str(value)[:900]
        for key in ('urls','target_urls'):
            if key in item:row[key]=[str(v)[:600] for v in item[key][:10]]
        if item.get('type')=='plan':
            d=item.get('decision',{});a=item.get('admitted',{})
            row.update(explanation=str(d.get('explanation',''))[:1000],action=d.get('action'),
                       coverage_gaps=[str(v)[:200] for v in d.get('coverage_gaps',[])[:8]],
                       queries=[str(q.get('query',''))[:350] for q in a.get('queries',[])[:5]],
                       inspect_urls=[str(u)[:600] for u in a.get('inspect_urls',[])[:10]],
                       high_reasoning=bool(a.get('high_reasoning')))
        events.append(row)
    # Prefer recent receipts (including the stop); preserve their original order.
    kept=[];size=0
    for row in reversed(events):
        cost=len(json.dumps(row,ensure_ascii=False).encode())
        if size+cost>max_bytes:break
        kept.append(row);size+=cost
    return {'events':list(reversed(kept)),'total_events':len(raw),'omitted_events':len(raw)-len(kept),
            'scope':state.get('trace_scope','partial_saved_actions'),
            'note':'Recorded tool actions and short decision explanations, not internal model reasoning. A started action without a completion receipt has an uncertain outcome. Historical missing actions are not reconstructed.'}
