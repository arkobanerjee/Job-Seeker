"""Publish only reviewed source files; never private state or credentials."""
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parent.parent
REPO='arkobanerjee/Job-Seeker'
BRANCH='codex/release-acceptance-and-retention'

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
        commit=api('POST','/git/commits',{'message':'Add safe evidence retention and record release acceptance','tree':tree['sha'],'parents':[parent]})
        if exists: api('PATCH','/git/refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False})
        else: api('POST','/git/refs',{'ref':'refs/heads/'+BRANCH,'sha':commit['sha']})
        prs=api('GET','/pulls?head=arkobanerjee:'+BRANCH+'&state=open')
        body=('Adds private immutable cold archives for terminal-run evidence, keeping the newest 20 runs and at least 30 days in active state. Active/resumable work, unresolved questions and outstanding delivery receipts are protected. Upload checksum and readback must pass before evidence leaves hot state; a pre-maintenance backup and conditional snapshot write protect concurrent changes. Catalog/registry/financial continuity databases remain intact. Adds weekday serialized maintenance, manual archive controls/downloads and visible budget reservations. This does not prune growing databases or delete cold archives.\n\nAdds isolated production-code recovery drills to CI and a repeatable explicit paid acceptance command with a $0.40 envelope in the existing cloud gate. Acceptance outputs and candidate data stay private. Operator documentation records the conservative no-refund/no-reset budget policy and release limitations.\n\nLive evidence: merged PR15 diagnostics passed; a fresh same-snapshot restore completed with budget, question, outbox, catalog and private preference continuity verified. The configured model completed 14 synthetic extraction cases and four reviewer probes. Strict result was 8/14, with zero false shortlists/misses within that sample. Four failures are exact unknown-string mismatches; two concern closed/signal category or title contracts. The original report is unchanged; no held-out real-market accuracy claim is made. Reviewer rejected two explicit blockers and marked two uncertain proposals manual_review.\n\nValidation: 85 Python tests, 17 Node tests, five isolated recovery drills and dashboard syntax checks pass. Drills inject external outcomes; they do not send real Telegram messages or prove all cloud/network failure behavior. Real old-run archival awaits eligible data; held-out real-source quality and growing-database capacity remain release work. No multi-worker benchmark or budget increase.')
        pr=prs[0] if prs else api('POST','/pulls',{'title':'Add evidence retention and record live acceptance results','head':BRANCH,'base':'main','body':body,'draft':True})
        api('PATCH','/pulls/'+str(pr['number']),{'title':'Add evidence retention and record live acceptance results','body':body})
        print(json.dumps({'url':pr['html_url'],'commit':commit['sha'],'files':len(entries)}))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,ValueError) else 'Publication failed: '+type(exc).__name__)
        raise SystemExit(1)
