"""Publish only reviewed source files; never private state or credentials."""
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parent.parent
REPO='arkobanerjee/Job-Seeker'
BRANCH='codex/output-contract-and-legacy-maintenance'

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
        commit=api('POST','/git/commits',{'message':'Clarify finding contracts and support legacy maintenance snapshots','tree':tree['sha'],'parents':[parent]})
        if exists: api('PATCH','/git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False})
        else: api('POST','/git/refs',{'ref':'refs/heads/'+BRANCH,'sha':commit['sha']})
        prs=api('GET','/pulls?head=arkobanerjee:'+BRANCH+'&state=open')
        body=('New model findings explicitly distinguish stated vs unknown language/authorization facts. Explicit unknown values receive canonical display text with the original explanation preserved; legacy records are not silently reclassified. Retrieved closed postings remain excluded reference records with closure reasons/evidence, structured ATS titles take precedence, and validated signal-only outcomes are distinct from vacancies. The versioned scorer follows this contract without changing the original synthetic labels/report.\n\nFixes live maintenance failure on legacy question databases lacking the cancelled column: all unanswered legacy questions conservatively protect their runs. The original live failure archived no data. Existing serialized notification recovery migrated the live schema, and the maintenance retry passed with no eligible old runs. Adds regression coverage for restored legacy snapshots.\n\nAcceptance can now take a private frozen case file, bounded envelope and explicit reviewer probes, validates limits before reserving funds, and saves private prompt/settings snapshots and a case-set hash. A separate six-case real-source evaluation frozen before generation passed 6/6 extraction/validation checks (four retrieved pages, two 404s). This small selected set is not general search recall or independently labelled market accuracy. Reviewer probes returned one reject and three manual reviews, with no unconditional accepts. The original 8/14 synthetic result is unchanged.\n\nValidation: 91 Python tests, 17 Node tests, five isolated recovery drills and dashboard syntax checks pass. Live evaluation used a $0.25 cloud envelope inside the existing $5 gate; no allowance increase, outreach, application or multi-worker benchmark. Raw source text, labels, candidate data and predictions remain private. Broader route acceptance and naturally aged-data archival are still operational limitations.')
        pr=prs[0] if prs else api('POST','/pulls',{'title':'Clarify output contracts and fix legacy maintenance compatibility','head':BRANCH,'base':'main','body':body,'draft':True})
        api('PATCH','/pulls/'+str(pr['number']),{'title':'Clarify output contracts and fix legacy maintenance compatibility','body':body})
        print(json.dumps({'url':pr['html_url'],'commit':commit['sha'],'files':len(entries)}))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,ValueError) else 'Publication failed: '+type(exc).__name__)
        raise SystemExit(1)
