"""Publish only reviewed source files; never private state or credentials."""
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parent.parent
REPO='arkobanerjee/Job-Seeker'
BRANCH='codex/dashboard-run-controls'

def main():
    values=dotenv_values(ROOT/'.env'); token=values.get('GITHUB_DEPLOY_TOKEN')
    if not token: raise ValueError('GITHUB_DEPLOY_TOKEN missing')
    files=[]
    for directory in ('job_seeker','tests','cloud','scripts','.github','prompts'):
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.js','.toml','.json','.yml','.md'))
    files.extend(ROOT/p for p in ('.gitignore','.env.example','README.md','DEPLOYMENT.md','config.toml','profile.example.md','pyproject.toml','requirements.lock'))
    entries=[{'path':p.relative_to(ROOT).as_posix(),'mode':'100644','type':'blob','content':p.read_text(encoding='utf-8')} for p in files]
    secret_values=[v for k,v in values.items() if v and len(v)>12 and any(s in k for s in ('TOKEN','KEY'))]
    if any(v in e['content'] for e in entries for v in secret_values): raise ValueError('A credential was detected in publication files')
    base='https://api.github.com/repos/'+REPO
    with httpx.Client(headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'},timeout=60,trust_env=False) as client:
        def api(method,path,body=None):
            r=client.request(method,base+path,json=body)
            if r.status_code not in (200,201): raise ValueError('GitHub publication failed: '+method+' '+path.split('?')[0]+' HTTP '+str(r.status_code))
            return r.json()
        head=client.get(base+'/git/ref/heads/'+BRANCH)
        exists=head.status_code==200
        if not exists and head.status_code!=404: raise ValueError('Cannot inspect publication branch')
        parent=head.json()['object']['sha'] if exists else api('GET','/git/ref/heads/main')['object']['sha']
        tree_base=api('GET','/git/commits/'+parent)['tree']['sha']
        tree=api('POST','/git/trees',{'base_tree':tree_base,'tree':entries})
        commit=api('POST','/git/commits',{'message':'Record and display job discovery evidence paths','tree':tree['sha'],'parents':[parent]})
        if exists: api('PATCH','/git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False})
        else: api('POST','/git/refs',{'ref':'refs/heads/'+BRANCH,'sha':commit['sha']})
        prs=api('GET','/pulls?head=arkobanerjee:'+BRANCH+'&state=open')
        body=('Adds authenticated run history, pending questions, dashboard answer-and-continue, and safe continuation controls for interrupted cloud runs. Summaries expose progress and usage estimates without prompts or raw page text. Answers validate the stored revision and cannot replace an accepted answer.\n\nWeekend scheduling is disabled on main as requested; this change also adds a runtime weekend guard. Multi-worker experiments remain deferred until the single-worker product is finished.\n\nValidation: 44 Python tests and 11 Node tests pass, covering history privacy, stale/conflicting answers, authentication and safe continuation. Dashboard script syntax checked. No paid search or model calls were made. Live dashboard acceptance remains pending after merge; the wider product is still incomplete.')
        pr=prs[0] if prs else api('POST','/pulls',{'title':'Show job discovery queries and evidence paths','head':BRANCH,'base':'main','body':body,'draft':True})
        api('PATCH','/pulls/'+str(pr['number']),{'title':'Answer questions and inspect saved runs from the dashboard','body':body})
        print(json.dumps({'url':pr['html_url'],'commit':commit['sha'],'files':len(entries)}))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,ValueError) else 'Publication failed: '+type(exc).__name__)
        raise SystemExit(1)
