"""Authenticated cloud state transfer. Only explicit allowlisted data enters archives."""
import io
import json
import os
import zipfile
from pathlib import PurePosixPath
from uuid import uuid4
import httpx
from .settings import ROOT,load_settings
from .catalog import Catalog
from .budget import Ledger

MAX_SIZE=20_000_000

def allowed(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name: return False
    if name in ('config.toml','prompts/master.md','private/profile.md','private/resume.md'): return True
    if p.parts[0:1]!=('runs',): return False
    if name in ('runs/budget.sqlite3','runs/catalog.sqlite3','runs/questions.sqlite3','runs/registry.sqlite3','runs/outbox.sqlite3'): return True
    return len(p.parts)==3 and len(p.parts[1])==32 and all(c in '0123456789abcdef' for c in p.parts[1]) and p.suffix in ('.json','.md')

def pack(root=ROOT):
    stream=io.BytesIO(); total=0
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        candidates=[root/'config.toml',root/'prompts/master.md',root/'private/profile.md',root/'private/resume.md']
        candidates+=list((root/'runs').rglob('*'))
        for path in candidates:
            name=path.relative_to(root).as_posix()
            if path.is_file() and not path.is_symlink() and allowed(name):
                total+=path.stat().st_size
                if total>MAX_SIZE: raise ValueError('Cloud state exceeds 20 MB; archive old runs before syncing')
                archive.write(path,name)
    return stream.getvalue()

def unpack(data,root=ROOT):
    if len(data)>MAX_SIZE: raise ValueError('State archive too large')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries=archive.infolist()
        if sum(x.file_size for x in entries)>MAX_SIZE or len(entries)>2000: raise ValueError('State archive too large')
        if len({x.filename for x in entries})!=len(entries): raise ValueError('Duplicate archive paths')
        if any(not allowed(x.filename) for x in entries): raise ValueError('Unexpected archive path')
        for entry in entries:
            target=root/entry.filename
            if not target.resolve().is_relative_to(root.resolve()): raise ValueError('Unsafe archive destination')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.read(entry))

class Cloud:
    def __init__(self):
        from dotenv import load_dotenv
        load_dotenv(ROOT/'.env',override=False)
        self.url=os.getenv('JOB_SEEKER_URL','').rstrip('/')
        self.token=os.getenv('JOB_SEEKER_APP_TOKEN','')
        if not self.url.startswith('https://') or not self.token: raise ValueError('Set JOB_SEEKER_URL and JOB_SEEKER_APP_TOKEN')

    def request(self,path,method='GET',body=None,binary=False,return_etag=False,expected_etag=None):
        from . import telemetry as audit
        import time
        state=audit.ACTIVE.get();started=time.monotonic()
        # Log upload never logs itself. No headers, bodies, credentials or endpoint tokens.
        row=None if path.startswith('evaluation/') else audit.start(state,'cloudflare','state_api',route=path.split('/')[0],method=method)
        try:
            value=self._request(path,method,body,binary,return_etag,expected_etag)
            audit.finish(state,row,'success',duration_ms=round((time.monotonic()-started)*1000,2))
            return value
        except Exception as exc:
            audit.finish(state,row,'failed',error_type=type(exc).__name__,duration_ms=round((time.monotonic()-started)*1000,2));raise

    def _request(self,path,method='GET',body=None,binary=False,return_etag=False,expected_etag=None):
        try:
            with httpx.Client(timeout=60,trust_env=False,follow_redirects=False) as client:
                response=client.request(method,self.url+'/api/'+path,headers={'Authorization':'Bearer '+self.token,
                    'Content-Type':'application/zip' if binary else 'application/json',**({'If-Match':expected_etag} if expected_etag else {})},content=body if binary else None,json=body if not binary else None)
            if response.status_code!=200: raise ValueError('Cloud request failed: HTTP '+str(response.status_code))
            if return_etag:return response.content,response.headers.get('etag')
            return response.content if method=='GET' and (path=='state' or path.startswith(('backup/','run-archive/'))) else response.json()
        except httpx.HTTPError: raise ValueError('Cloud connection failed') from None

    def sync(self):
        self.request('state','PUT',pack(),True)
        self.sync_views()

    def sync_views(self,root=None):
        root=root or ROOT
        catalog=Catalog(root/'runs'/'catalog.sqlite3')
        self.request('catalog','PUT',catalog.list())
        from .history import run_history
        self.request('runs','PUT',run_history(root/'runs'))
        # Only changed per-run exports are uploaded; old logs remain individually downloadable.
        import hashlib
        uploaded=getattr(self,'_uploaded_evaluations',{})
        for path in (root/'runs').glob('*/evaluation.json'):
            data=path.read_text(encoding='utf-8');digest=hashlib.sha256(data.encode()).hexdigest()
            if uploaded.get(path.parent.name)==digest:continue
            self.request('evaluation/'+path.parent.name,'PUT',json.loads(data));uploaded[path.parent.name]=digest
        self._uploaded_evaluations=uploaded
        from .outbox import Outbox
        self.request('notifications','PUT',Outbox(root/'runs/outbox.sqlite3').summary())
        from .registry import Registry
        registry=Registry(root/'runs/registry.sqlite3'); registry.import_runs(root/'runs')
        self.request('registry','PUT',registry.export())
        from .questions import Questions
        for question in Questions(root/'runs/questions.sqlite3').pending():
            self.request('question','POST',question)

    def settings(self):
        files={name:(ROOT/name).read_text(encoding='utf-8') for name in ('config.toml','prompts/master.md','private/profile.md','private/resume.md') if (ROOT/name).exists()}
        self.request('settings','PUT',files)

def bootstrap():
    from .runner import single_worker
    cloud=Cloud()
    with single_worker(ROOT/'runs'):
        catalog=Catalog(ROOT/'runs'/'catalog.sqlite3'); catalog.import_runs(ROOT/'runs')
        reserved=Ledger(ROOT/'runs'/'budget.sqlite3','migration').summary()['initial_stage_reserved_usd']
        # This endpoint cannot reset an existing cloud budget.
        cloud.request('initialize','POST',{'already_reserved':reserved})
        cloud.sync()
        cloud.settings()

def record_cloud_failure(root,before,resume,exc):
    """Retain an initial checkpoint failure without exposing exception payloads."""
    from datetime import datetime,timezone
    from .research import write_json
    import re
    receipt=re.fullmatch(r'Cloud request failed: HTTP (\d{3})',str(exc))
    failure=('Publishing progress failed (HTTP '+receipt.group(1)+').' if receipt else
             'The worker could not save or publish its progress.')+' Saved evidence is retained. Inspect the execution log before continuing.'
    for checkpoint in (root/'runs').glob('*/checkpoint.json'):
        if checkpoint.parent.name in before and checkpoint.parent.name!=resume:continue
        state=json.loads(checkpoint.read_text(encoding='utf-8'))
        if state.get('status')!='running':continue
        state.update(status='failed',error_type=type(exc).__name__,finished_at=datetime.now(timezone.utc).isoformat(),failure_reason=failure)
        write_json(checkpoint,state)


def run_cloud(resume=None,monitor=False,scheduled=False,operation="discovery"):
    # Only the serialized GitHub workflow may own this state. No parallel local writes.
    if os.getenv('GITHUB_ACTIONS')!='true': raise ValueError('Cloud worker runs through the serialized GitHub Actions workflow')
    if not resume: os.environ['JOB_SEEKER_SCHEDULED']='true' if scheduled else 'false'
    if not resume: os.environ['JOB_SEEKER_MONITORING']='true' if monitor else 'false'
    cloud=Cloud(); initial,initial_etag=cloud.request('state',return_etag=True); unpack(initial)
    for name,content in cloud.request('settings').items():
        if name not in ('config.toml','prompts/master.md','private/profile.md','private/resume.md') or not isinstance(content,str): raise ValueError('Unexpected cloud settings')
        target=ROOT/name; target.parent.mkdir(exist_ok=True,parents=True); target.write_text(content,encoding='utf-8')
    settings,_=load_settings()
    from .company_discovery import operation_settings
    if not resume: settings=operation_settings(settings,operation)
    if scheduled:
        from .monitoring import scheduled_cap
        from .questions import Questions
        from datetime import datetime
        from zoneinfo import ZoneInfo
        reason=None
        if not settings.monitoring.schedule_enabled: reason='schedule_disabled'
        elif datetime.now(ZoneInfo('Europe/Berlin')).weekday()>=5: reason='weekend'
        elif Questions(ROOT/'runs/questions.sqlite3').pending(): reason='waiting_for_user'
        if reason:
            cloud.request('monitor-status','PUT',{'status':'skipped','reason':reason})
            return None,{'status':'skipped','reason':reason,'findings':[]}
        date=datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat()
        claim=cloud.request('schedule-claim','POST',{'date':date})
        if not claim.get('claimed'): return None,{'status':'skipped','reason':'already_checked_today','findings':[]}
        settings.limits.run_usd=min(settings.limits.run_usd,settings.monitoring.daily_run_usd)
    from .health import inspect_snapshot
    health=inspect_snapshot(initial)
    health['state_etag']=initial_etag or ''
    cloud.request('health','PUT',health)
    if health['status']=='blocked':raise ValueError('Private state health check blocked research; inspect storage diagnostics before retrying')
    backup_cloud(cloud,initial)
    # Reserve the entire run ceiling before any paid action. A killed runner cannot
    # reset global accounting by losing its last snapshot. No automatic refunds.
    if not resume:
        cloud.request('reserve','POST',{'id':uuid4().hex,'amount':settings.limits.run_usd})
    else:
        import re
        if not re.fullmatch(r'[a-f0-9]{32}',resume) or not (ROOT/'runs'/resume/'checkpoint.json').exists(): raise ValueError('Unknown cloud run')
        checkpoint=json.loads((ROOT/'runs'/resume/'checkpoint.json').read_text(encoding='utf-8'))
        if not checkpoint.get('cloud_envelope'): raise ValueError('Run has no recorded cloud budget envelope')
        from .questions import Questions
        questions=Questions(ROOT/'runs/questions.sqlite3')
        for question in questions.pending():
            answer=cloud.request('answer/'+question['id'])
            if answer.get('answer') is not None: questions.answer(question['id'],question['revision'],answer['answer'])
    catalog=Catalog(ROOT/'runs'/'catalog.sqlite3')
    known={x['id'] for x in catalog.list()}
    for ident,decision in cloud.request('decisions').items():
        if ident in known: catalog.decide(ident,decision['decision'],decision.get('note',''))
    from .runner import run
    before={p.parent.name for p in (ROOT/'runs').glob('*/checkpoint.json')}
    try:
        folder,result=run(resume=resume,operation=operation,on_checkpoint=cloud.sync,control=lambda ident:cloud.request("control/"+ident).get("action","run"))
        cloud.sync()
    except Exception as exc:
        # Initial/final checkpoint failures occur outside the research loop's handler.
        # Publish a safe failure receipt independently of optional evaluation uploads.
        record_cloud_failure(ROOT,before,resume,exc)
        try:cloud._request('state','PUT',pack(),True)
        except Exception:pass
        try:
            from .history import run_history
            cloud._request('runs','PUT',run_history(ROOT/'runs'))
        except Exception:pass
        raise
    if scheduled: cloud.request('monitor-status','PUT',{'status':result['status'],'run_id':result['run_id']})
    return folder,result

def backup_cloud(cloud=None,data=None):
    from .backups import verify_archive
    cloud=cloud or Cloud();data=data if data is not None else cloud.request('state')
    digest=verify_archive(data);ident=uuid4().hex
    manifest=cloud.request('backup/'+ident,'PUT',data,True)
    if manifest['sha256']!=digest:raise ValueError('Uploaded backup checksum mismatch')
    return manifest

def restore_cloud(ident):
    if os.getenv('GITHUB_ACTIONS')!='true':raise ValueError('Restore through the serialized workflow')
    import re
    if not re.fullmatch(r'[a-f0-9]{32}',ident or ''):raise ValueError('Invalid backup ID')
    from .backups import verify_archive,restore_payload
    cloud=Cloud();manifest=next((x for x in cloud.request('backups') if x['id']==ident),None)
    if not manifest:raise ValueError('Unknown retained backup')
    data=cloud.request('backup/'+ident);verify_archive(data,manifest['sha256'])
    current,etag=cloud.request('state',return_etag=True)
    if not etag:raise ValueError('Missing state version; restore aborted')
    restored=restore_payload(data,current)
    backup_cloud(cloud,current)
    cloud.request('state','PUT',restored,True,expected_etag=etag)
    unpack(restored);cloud.sync()


def maintain_cloud():
    if os.getenv('GITHUB_ACTIONS')!='true':raise ValueError('Maintenance through the serialized workflow')
    import tempfile
    from pathlib import Path
    from .retention import archive_terminal_runs
    cloud=Cloud();current,etag=cloud.request('state',return_etag=True)
    if not etag:raise ValueError('Missing state version; maintenance aborted')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);unpack(current,root)
        from .retention import candidates
        ids=candidates(root)
        if not ids:return {'archived':0,'policy':'Keep newest 20 runs and at least 30 days; terminal runs only'}
        backup_cloud(cloud,current)
        ids,data=archive_terminal_runs(cloud,root)
        cloud.request('state','PUT',data,True,expected_etag=etag)
        cloud.sync_views(root)
        return {'archived':len(ids),'run_ids':ids}


def observe_cloud_boards(scheduled=False):
    if os.getenv('GITHUB_ACTIONS')!='true':raise ValueError('Board observations through the serialized workflow')
    import tempfile,tomllib
    from pathlib import Path
    from datetime import datetime,timezone
    from zoneinfo import ZoneInfo
    from .settings import Settings
    from .registry import Registry
    from .boards import observe,board_targets
    from .health import inspect_snapshot
    from .research import write_json
    cloud=Cloud();settings=Settings.model_validate(tomllib.loads(cloud.request('settings')['config.toml']))
    if not settings.monitoring.board_observations:return {'status':'skipped','reason':'board_observations_disabled'}
    if scheduled and (not settings.monitoring.schedule_enabled or datetime.now(ZoneInfo('Europe/Berlin')).weekday()>=5):return {'status':'skipped','reason':'schedule_disabled_or_weekend'}
    current,etag=cloud.request('state',return_etag=True)
    if not etag or inspect_snapshot(current)['status']=='blocked':raise ValueError('State health/version blocks board observations')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);unpack(current,root);registry=Registry(root/'runs/registry.sqlite3')
        if not board_targets(registry,settings.monitoring.board_urls,settings.monitoring.max_boards):return {'status':'skipped','reason':'no_known_supported_boards'}
        backup_cloud(cloud,current)
        ident=uuid4().hex;started=datetime.now(timezone.utc).isoformat()
        result=observe(registry,ident,settings.monitoring.board_urls,settings.monitoring.max_boards)
        result.update(started_at=started,finished_at=datetime.now(timezone.utc).isoformat())
        folder=root/'runs'/ident;folder.mkdir()
        write_json(folder/'result.json',result)
        write_json(folder/'checkpoint.json',{**result,'config':settings.model_dump(),'cloud_envelope':False,'scheduled':scheduled,'queue':[],'cache':{},'limitations':['Board counts only; no job-fit assessment or hiring probability.']})
        from .telemetry import save
        save({**result,'folder':str(folder)})
        cloud.request('state','PUT',pack(root),True,expected_etag=etag)
        cloud.sync_views(root)
        return {k:result[k] for k in ('run_id','status','mode','targets','searches','model_calls')}

def retry_notifications():
    if os.getenv('GITHUB_ACTIONS')!='true':raise ValueError('Retry through the serialized GitHub workflow')
    from .questions import Questions,send_question
    from .outbox import Outbox
    import tomllib
    cloud=Cloud();unpack(cloud.request('state'))
    config=tomllib.loads(cloud.request('settings')['config.toml'])
    if not config.get('notifications',{}).get('telegram'):return
    outbox=Outbox(ROOT/'runs/outbox.sqlite3');outbox.drain(before_send=cloud.sync)
    questions=Questions(ROOT/'runs/questions.sqlite3')
    for question in questions.pending():
        try:send_question(questions,question,on_checkpoint=cloud.sync)
        except ValueError:pass
    cloud.sync()

def main():
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['bootstrap','run','company','monitor','scheduled','notifications','backup','restore','diagnostics','maintenance','boards','scheduled-boards','settings']); parser.add_argument('--run-id'); parser.add_argument('--backup-id')
    args=parser.parse_args()
    if args.command in ('boards','scheduled-boards'):print(json.dumps(observe_cloud_boards(args.command=='scheduled-boards')))
    elif args.command=='maintenance':print(json.dumps(maintain_cloud()))
    elif args.command=='diagnostics':
        from .health import diagnose_cloud
        report=diagnose_cloud(Cloud());print(json.dumps(report))
        if report['status']=='blocked':raise SystemExit(1)
    elif args.command=='backup': print('Private backup created: '+backup_cloud()['id'])
    elif args.command=='restore': restore_cloud(args.backup_id); print('Research restored; current spending ledger and settings retained')
    elif args.command=='notifications': retry_notifications(); print('Notification recovery attempted; no research rerun')
    elif args.command=='bootstrap': bootstrap(); print('Private cloud state initialized')
    elif args.command=='settings':
        from .settings import render_prompt
        settings,base=load_settings(); render_prompt(settings,base)
        Cloud().settings(); print('Private cloud settings updated for subsequent runs')
    else:
        _,result=run_cloud(args.run_id,monitor=args.command in ('monitor','scheduled'),scheduled=args.command=='scheduled',operation='company' if args.command=='company' else 'discovery')
        print(json.dumps({'run_id':result.get('run_id'),'status':result['status'],'findings':len(result['findings'])}))
        if result.get('error_type'): raise SystemExit(1)

if __name__=='__main__': main()
