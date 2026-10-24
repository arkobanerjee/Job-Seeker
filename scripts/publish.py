"""Publish only reviewed source files; never private state or credentials."""
import argparse
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parent.parent
REPO='arkobanerjee/Job-Seeker'
BRANCH='codex/per-run-budget-and-workspace-cleanup'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--branch',default=BRANCH);parser.add_argument('--title',required=True);parser.add_argument('--body-file',type=Path,required=True);args=parser.parse_args()
    if not args.branch.startswith('codex/') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-_' for c in args.branch):raise ValueError('Invalid publication branch')
    body=args.body_file.read_text(encoding='utf-8')
    values=dotenv_values(ROOT/'.env'); token=values.get('GITHUB_DEPLOY_TOKEN')
    if not token: raise ValueError('GITHUB_DEPLOY_TOKEN missing')
    files=[]
    for directory in ('job_seeker','tests','cloud','scripts','.github','prompts','experiments','docs','examples'):
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.js','.toml','.json','.yml','.md'))
    files.extend(ROOT/p for p in ('.gitignore','.env.example','README.md','config.toml','pyproject.toml','requirements.lock'))
    entries=[{'path':p.relative_to(ROOT).as_posix(),'mode':'100644','type':'blob','content':p.read_text(encoding='utf-8')} for p in files]
    secret_values=[v for k,v in values.items() if v and len(v)>12 and any(s in k for s in ('TOKEN','KEY'))]
    if any(v in e['content'] for e in entries+[{'content':body}] for v in secret_values): raise ValueError('A credential was detected in publication files')
    base='https://api.github.com/repos/'+REPO
    with httpx.Client(headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'},timeout=60,trust_env=False) as client:
        def api(method,path,body=None):
            r=client.request(method,base+path,json=body)
            if r.status_code not in (200,201): raise ValueError('GitHub publication failed: '+method+' '+path.split('?')[0]+' HTTP '+str(r.status_code))
            return r.json()
        branch=args.branch
        head=client.get(base+'/git/ref/heads/'+branch)
        exists=head.status_code==200
        if not exists and head.status_code!=404: raise ValueError('Cannot inspect publication branch')
        parent=head.json()['object']['sha'] if exists else api('GET','/git/ref/heads/main')['object']['sha']
        tree_base=api('GET','/git/commits/'+parent)['tree']['sha']
        existing={x['path'] for x in api('GET','/git/trees/'+tree_base+'?recursive=1')['tree']}
        moved=('USER_GUIDE.md','DEPLOYMENT.md','comparison-plan.md','adaptive-evaluation.md','implementation-plan.md','completion-status.md','profile.example.md')
        entries.extend({'path':name,'mode':'100644','type':'blob','sha':None} for name in moved if name in existing)
        tree=api('POST','/git/trees',{'base_tree':tree_base,'tree':entries})
        commit=api('POST','/git/commits',{'message':args.title,'tree':tree['sha'],'parents':[parent]})
        if exists: api('PATCH','/git/refs/heads/'+branch,{'sha':commit['sha'],'force':False})
        else: api('POST','/git/refs',{'ref':'refs/heads/'+branch,'sha':commit['sha']})
        prs=api('GET','/pulls?head=arkobanerjee:'+branch+'&state=open')

        pr=prs[0] if prs else api('POST','/pulls',{'title':args.title,'head':branch,'base':'main','body':body,'draft':True})
        api('PATCH','/pulls/'+str(pr['number']),{'title':args.title,'body':body})
        print(json.dumps({'url':pr['html_url'],'commit':commit['sha'],'files':len(entries)}))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,ValueError) else 'Publication failed: '+type(exc).__name__)
        raise SystemExit(1)
