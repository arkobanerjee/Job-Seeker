"""Publish only reviewed source files; never private state or credentials."""
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parent.parent
REPO='arkobanerjee/Job-Seeker'
BRANCH='codex/board-observations-and-route-acceptance'

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
        commit=api('POST','/git/commits',{'message':'Collect bounded ATS observations and validate optional routes','tree':tree['sha'],'parents':[parent]})
        if exists: api('PATCH','/git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False})
        else: api('POST','/git/refs',{'ref':'refs/heads/'+BRANCH,'sha':commit['sha']})
        prs=api('GET','/pulls?head=arkobanerjee:'+BRANCH+'&state=open')
        body=('Adds a separate bounded public ATS board-count path with no model, paid-search or budget-reservation calls. It derives supported boards from known ATS URLs and validated optional seeds, collapses duplicates, rotates oldest sources and caps reads. Weekday collection respects schedule settings and can continue when paid research hits its gate. It uses the serialized workflow, state health/version checks and a private pre-write backup. Dashboard control and history distinguish observations from job-fit research. Unavailable boards never become zero counts.\n\nBoard comparisons now require actual distinct UTC dates and comparable provider, tenant, API and sample provenance. A changed collection policy starts a new baseline rather than inventing growth. Missing provenance and invalid counts fail closed. A real read produced one private first-day baseline; a second board was unavailable. Live multi-date acceptance awaits real elapsed time.\n\nAdds an explicit two-call private route acceptance helper with a $0.04 envelope in the unchanged $5 gate. Focused real-source competitor and same-claim corroboration probes passed quote checks. Publisher independence remained unverified; issuer/investor announcements are not independent reporting. Optional discovery flags were not enabled by this test. The selected positive probes are not broad route-accuracy evidence. Raw captures and results remain private.\n\nValidation: 100 Python tests, 18 Node tests, five recovery drills and dashboard syntax checks pass. Coverage includes scope changes, UTC dates, unavailable vs zero counts, disabled-observer guards, conditional snapshot writes without reservations, quote checks and distinct workflow dispatch. No multi-worker benchmark, allowance increase or fabricated historical observations.')
        pr=prs[0] if prs else api('POST','/pulls',{'title':'Add model-free board observations and optional-route acceptance','head':BRANCH,'base':'main','body':body,'draft':True})
        api('PATCH','/pulls/'+str(pr['number']),{'title':'Add model-free board observations and optional-route acceptance','body':body})
        print(json.dumps({'url':pr['html_url'],'commit':commit['sha'],'files':len(entries)}))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,ValueError) else 'Publication failed: '+type(exc).__name__)
        raise SystemExit(1)
