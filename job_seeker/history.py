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
            'mode':'monitor' if state.get('config',{}).get('monitoring',{}).get('enabled') else 'discovery',
            'scheduled':state.get('scheduled',False),'can_resume':bool(state.get('cloud_envelope')) and state['status'] in ('partial','failed'),
            'observed_estimate_usd':result.get('budget',{}).get('observed_estimate_usd'),
            'limitations':state.get('limitations',[])})
    return sorted(rows,key=lambda x:x.get('started_at') or '',reverse=True)[:250]
