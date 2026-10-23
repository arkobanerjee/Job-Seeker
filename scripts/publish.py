"""Publish only reviewed source files; never private state or credentials."""
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parent.parent
REPO='arkobanerjee/Job-Seeker'
BRANCH='codex/corroboration-and-private-backups'

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
        commit=api('POST','/git/commits',{'message':'Add signal corroboration and private backup restore','tree':tree['sha'],'parents':[parent]})
        if exists: api('PATCH','/git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False})
        else: api('POST','/git/refs',{'ref':'refs/heads/'+BRANCH,'sha':commit['sha']})
        prs=api('GET','/pulls?head=arkobanerjee:'+BRANCH+'&state=open')
        body=('Adds bounded, independent-context comparison of company signals collected from different sources. Supporting and contradictory verdicts require quotes from both excerpts. Different hostnames alone do not establish publisher independence; configured publisher mappings distinguish known ownership. Corroboration is configurable and disabled by default, sharing existing call and spending limits.\n\nAdds authenticated private R2 backups with SHA-256 integrity metadata, five-snapshot retention, dashboard controls and serialized workflow modes. Research runs take a snapshot before work. Restore validates archives, preserves current spending records, notification receipts, questions, preferences and paused/waiting task continuity, creates a pre-restore backup and uses a state version check to reject concurrent changes. This does not remove the active archive size limit or replace an off-account backup.\n\nValidation: 73 Python tests and 15 Node tests pass, including corroboration quote checks, an integrated mocked-provider run, backup retention, archive integrity, restore continuity and concurrent-update rejection. Dashboard script syntax checked. No paid calls or live restore were performed for this batch. Live acceptance and final release evaluation remain pending.')
        pr=prs[0] if prs else api('POST','/pulls',{'title':'Corroborate company signals and add private backup/restore','head':BRANCH,'base':'main','body':body,'draft':True})
        api('PATCH','/pulls/'+str(pr['number']),{'title':'Corroborate company signals and add private backup/restore','body':body})
        print(json.dumps({'url':pr['html_url'],'commit':commit['sha'],'files':len(entries)}))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,ValueError) else 'Publication failed: '+type(exc).__name__)
        raise SystemExit(1)
