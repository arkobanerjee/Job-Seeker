"""Explicit deployment helper. Credentials are read locally and never logged."""
import argparse
import base64
import json
import secrets
import sys
from pathlib import Path
import httpx
from dotenv import dotenv_values,set_key

ROOT=Path(__file__).resolve().parent.parent
REPO='arkobanerjee/Job-Seeker'

def call(client,method,url,**kwargs):
    response=client.request(method,url,**kwargs)
    if response.status_code not in (200,201,204):
        raise RuntimeError(f'Deployment request failed: HTTP {response.status_code}; check token permissions and account setup')
    return response.json() if response.content else {}

def deploy_worker(values,github_dispatch=False):
    account=values.get('CLOUDFLARE_ACCOUNT_ID'); token=values.get('CLOUDFLARE_API_TOKEN')
    if not account or not token: raise ValueError('Missing Cloudflare account or deployment token')
    app=values.get('JOB_SEEKER_APP_TOKEN')
    if not app:
        app=secrets.token_urlsafe(32); set_key(ROOT/'.env','JOB_SEEKER_APP_TOKEN',app); values['JOB_SEEKER_APP_TOKEN']=app
    base=f'https://api.cloudflare.com/client/v4/accounts/{account}'
    with httpx.Client(headers={'Authorization':'Bearer '+token},timeout=60,trust_env=False) as client:
        sub=call(client,'GET',base+'/workers/subdomain').get('result',{}).get('subdomain')
        if not sub: raise ValueError('Register your workers.dev subdomain in Cloudflare before deploying')
        r2_headers={'Authorization':'Bearer '+(values.get('R2_API_TOKEN') or token)}
        buckets=call(client,'GET',base+'/r2/buckets',headers=r2_headers).get('result',{}).get('buckets',[])
        if not any(x.get('name')=='job-seeker-private' for x in buckets):
            call(client,'POST',base+'/r2/buckets',headers=r2_headers,json={'name':'job-seeker-private'})
        bindings=[{'type':'r2_bucket','name':'STATE','bucket_name':'job-seeker-private'},
                  {'type':'secret_text','name':'APP_TOKEN','text':app},
                  {'type':'plain_text','name':'GITHUB_REPOSITORY','text':REPO},
                  {'type':'plain_text','name':'GITHUB_REF','text':'main'}]
        if github_dispatch and values.get('GITHUB_DEPLOY_TOKEN'): bindings.append({'type':'secret_text','name':'GITHUB_TOKEN','text':values['GITHUB_DEPLOY_TOKEN']})
        # Preserve the already configured owner identity and webhook verification.
        for name in ('TELEGRAM_WEBHOOK_SECRET','TELEGRAM_CHAT_ID'):
            if values.get(name): bindings.append({'type':'secret_text','name':name,'text':values[name]})
        metadata={'main_module':'worker.js','compatibility_date':'2026-10-23','bindings':bindings}
        parts={'metadata':(None,json.dumps(metadata),'application/json')}
        for name in ('worker.js','page.js','questions.js','controls.js'):
            parts[name]=(name,(ROOT/'cloud'/name).read_text(encoding='utf-8'),'application/javascript+module')
        call(client,'PUT',base+'/workers/scripts/job-seeker',files=parts)
        call(client,'POST',base+'/workers/scripts/job-seeker/subdomain',json={'enabled':True})
    url=f'https://job-seeker.{sub}.workers.dev'
    set_key(ROOT/'.env','JOB_SEEKER_URL',url); values['JOB_SEEKER_URL']=url
    print('Deployed authenticated dashboard: '+url)

def github_secrets(values):
    from nacl.public import PublicKey,SealedBox
    from nacl.encoding import Base64Encoder
    token=values.get('GITHUB_DEPLOY_TOKEN')
    if not token: raise ValueError('Missing GITHUB_DEPLOY_TOKEN')
    base='https://api.github.com/repos/'+REPO
    with httpx.Client(headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'},timeout=30,trust_env=False) as client:
        # Restrict the production environment to the trusted deployment branch.
        call(client,'PUT',base+'/environments/production',json={'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True}})
        policies=call(client,'GET',base+'/environments/production/deployment-branch-policies').get('branch_policies',[])
        if not any(x.get('name')=='main' for x in policies):
            call(client,'POST',base+'/environments/production/deployment-branch-policies',json={'name':'main','type':'branch'})
        repo=call(client,'GET',base); repo_id=repo['id']
        secret_base=f'https://api.github.com/repositories/{repo_id}/environments/production/secrets'
        pub=call(client,'GET',secret_base+'/public-key')
        box=SealedBox(PublicKey(pub['key'].encode(),Base64Encoder))
        for name in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','TAVILY_API_KEY','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID','JOB_SEEKER_URL','JOB_SEEKER_APP_TOKEN'):
            if values.get(name):
                encrypted=base64.b64encode(box.encrypt(values[name].encode())).decode()
                call(client,'PUT',secret_base+'/'+name,json={'encrypted_value':encrypted,'key_id':pub['key_id']})
                print('Configured environment secret: '+name)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['worker','github-secrets']); parser.add_argument('--enable-github-dispatch',action='store_true'); args=parser.parse_args()
    values=dotenv_values(ROOT/'.env')
    try:
        if args.action=='worker': deploy_worker(values,args.enable_github_dispatch)
        else: github_secrets(values)
    except Exception as exc:
        # Do not log provider exception bodies, request objects or local values.
        print(str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'Deployment failed: '+type(exc).__name__)
        sys.exit(1)

if __name__=='__main__': main()
