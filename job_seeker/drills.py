"""Isolated recovery drills against production code with injected external failures."""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from .runner import run,Assessment
from .research import Finding
from .sources import SourceTools,ServiceFailure
from .outbox import Outbox
from .telegram import DeliveryUncertain


def recovery_drills():
    checks=[]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'private').mkdir();(root/'prompts').mkdir()
        (root/'private/profile.md').write_text('Python and analytics. Basic German.')
        (root/'prompts/master.md').write_text('PROFILE {{profile}} RESUME {{resume}}')
        (root/'config.toml').write_text('[limits]\nmax_searches=1\nmax_pages=2\n[search]\nqueries=[{track="ai",query="synthetic drill"}]\n')
        url='https://synthetic.example/drill';quote='Applied AI Engineer develops Python RAG services and deployment automation.'
        counts={'search':0,'fetch':0,'model':0};fail=[True]
        def search(tools,query):
            if query not in tools.cache:
                counts['search']+=1;tools.searches+=1;tools.cache[query]=[{'url':url}];tools.allowed.add(url);tools.persist()
            return tools.cache[query]
        def fetch(tools,target):
            if target not in tools.records:
                counts['fetch']+=1;tools.fetches+=1;tools.records[target]={'url':url,'source_id':'drill','text':quote,'http_status':200,'observed_at':'2026-10-23T00:00:00+00:00','links':[]};tools.persist()
            return tools.records[target]
        def model(*args,**kwargs):
            counts['model']+=1
            if fail[0]:fail[0]=False;raise ServiceFailure('Injected interruption after saved search/page')
            return Assessment(source_type='employer',findings=[Finding(kind='vacancy',track='ai',company='SYNTHETIC',title='Applied AI Engineer',url=url,source_id='drill',evidence_quote=quote,fit='possible',fit_reason='Synthetic drill',language='unknown',location='unknown',eligibility='unknown',concerns=[])])
        with patch('job_seeker.runner.ROOT',root),patch.dict('os.environ',{'OPENAI_API_KEY':'synthetic','TAVILY_API_KEY':'synthetic','GITHUB_ACTIONS':'false','JOB_SEEKER_MONITORING':'false','JOB_SEEKER_SCHEDULED':'false'}),patch.object(SourceTools,'search',search),patch.object(SourceTools,'fetch',fetch),patch('job_seeker.runner.invoke_model',side_effect=model):
            folder,stopped=run(root/'config.toml')
            if stopped['status'] not in ('partial','failed'):raise AssertionError('Failure was not persisted')
            before=dict(counts);_,resumed=run(resume=folder.name)
            if resumed['status']!='completed' or counts['search']!=before['search'] or counts['fetch']!=before['fetch']:raise AssertionError('Restart repeated saved tools')
            checks.append({'check':'restart_saved_progress','status':'passed','search_repeats':0,'fetch_repeats':0,'interrupted_assessment_retried':True})
            before=dict(counts);folder,paused=run(root/'config.toml',control=lambda _: 'pause')
            if paused['status']!='paused' or counts!=before:raise AssertionError('Pause did not stop tools')
            _,continued=run(resume=folder.name,control=lambda _: 'run')
            if continued['status']!='completed':raise AssertionError('Paused task did not continue')
            checks.append({'check':'pause_and_continue','status':'passed'})
            before=dict(counts);folder,cancelled=run(root/'config.toml',control=lambda _: 'cancel')
            if cancelled['status']!='cancelled' or counts!=before:raise AssertionError('Cancellation did not stop tools')
            try:run(resume=folder.name)
            except ValueError:pass
            else:raise AssertionError('Cancelled task resumed')
            checks.append({'check':'cancel_is_terminal','status':'passed'})
        box=Outbox(root/'runs/outbox.sqlite3');box.enqueue('definite','Synthetic delivery drill')
        with patch('job_seeker.telegram.send',side_effect=ValueError('Injected rejected send')):
            try:box.deliver('definite')
            except ValueError:pass
        with patch('job_seeker.telegram.send',return_value=777) as send,patch('job_seeker.outbox.time.time',return_value=time.time()+7200):
            restarted=Outbox(box.path);restarted.drain();restarted.deliver('definite')
            if send.call_count!=1:raise AssertionError('Known successful delivery repeated')
        checks.append({'check':'delivery_failure_then_restart','status':'passed','successful_sends':1})
        box.enqueue('uncertain','Synthetic uncertain send')
        with patch('job_seeker.telegram.send',side_effect=DeliveryUncertain('Injected timeout')):
            try:box.deliver('uncertain')
            except DeliveryUncertain:pass
        with patch('job_seeker.telegram.send') as send:
            Outbox(box.path).drain()
            if send.called:raise AssertionError('Uncertain delivery automatically repeated')
        checks.append({'check':'uncertain_delivery_not_retried','status':'passed'})
    return {'checks':checks,'status':'passed','scope':'Production code in an isolated temporary workspace; network and provider failures injected. No real Telegram delivery or paid tools.'}


if __name__=='__main__':print(json.dumps(recovery_drills()))
