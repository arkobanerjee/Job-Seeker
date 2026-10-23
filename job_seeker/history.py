"""Dashboard summaries without prompts, page text or credentials."""
import json

def run_history(root):
    rows=[]
    for checkpoint in root.glob('*/checkpoint.json'):
        state=json.loads(checkpoint.read_text(encoding='utf-8'))
        result_path=checkpoint.parent/'result.json'
        result=json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {}
        rows.append({'run_id':state['run_id'],'status':state['status'],'started_at':state.get('started_at'),
            'finished_at':result.get('finished_at'),'findings':len(state.get('findings',[])),
            'searches':state.get('searches',0),'pages':state.get('fetches',0),'model_calls':state.get('model_calls',0),
            'error_type':state.get('error_type'),'notification_error':result.get('notification_error'),
            'mode':state.get('mode') or ('monitor' if state.get('config',{}).get('monitoring',{}).get('enabled') else 'discovery'),
            'scheduled':state.get('scheduled',False),'can_resume':bool(state.get('cloud_envelope')) and state['status'] in ('partial','failed','paused'),
            'observed_estimate_usd':result.get('budget',{}).get('observed_estimate_usd'),
            'activity':activity_summary(state),'limitations':state.get('limitations',[])})
    return sorted(rows,key=lambda x:x.get('started_at') or '',reverse=True)[:250]


def activity_summary(state):
    cache=state.get('cache',{})
    searches=[{'query':str(query),'results':len(results) if isinstance(results,list) else None,
               'urls':[r.get('url') for r in results[:5] if isinstance(r,dict)] if isinstance(results,list) else []}
              for query,results in cache.items()][:20]
    sources=[{'url':url,'http_status':record.get('http_status'),'error':record.get('error'),
              'observed_at':record.get('observed_at')}
             for url,record in state.get('sources',{}).items()][:40]
    count=state.get('searches',0)
    return {'summary':('Searched the web using Tavily.' if count else
                       'No new web searches. Saved sources may have been revisited.' if state.get('fetches') else
                       'No web searches or page fetches recorded.'),
            'searches':searches,'sources':sources,
            'note':'Saved observations; not a complete chronological action trace. Missing historical details cannot be reconstructed reliably.'}
