"""Bounded adapters for documented public Greenhouse and Lever GET APIs."""
import html
import json
import re
from urllib.parse import urlsplit

SLUG=re.compile(r"^[A-Za-z0-9_-]{1,100}$")
JOB=re.compile(r"^[A-Za-z0-9-]{1,100}$")

def endpoint(url):
    p=urlsplit(url);parts=p.path.strip('/').split('/');host=p.hostname
    if not parts or not SLUG.fullmatch(parts[0]):return None
    tenant=parts[0]
    if host in ('boards.greenhouse.io','job-boards.greenhouse.io'):
        if len(parts)==1:return ('greenhouse',tenant,None,f'https://boards-api.greenhouse.io/v1/boards/{tenant}/jobs')
        if len(parts)==3 and parts[1]=='jobs' and parts[2].isdigit():return ('greenhouse',tenant,parts[2],f'https://boards-api.greenhouse.io/v1/boards/{tenant}/jobs/{parts[2]}')
    if host in ('jobs.lever.co','jobs.eu.lever.co'):
        api='api.eu.lever.co' if host=='jobs.eu.lever.co' else 'api.lever.co'
        if len(parts)==1:return ('lever',tenant,None,f'https://{api}/v0/postings/{tenant}?mode=json&limit=100')
        if len(parts)==2 and JOB.fullmatch(parts[1]):return ('lever',tenant,parts[1],f'https://{api}/v0/postings/{tenant}/{parts[1]}?mode=json')
    return None

def parse(info,body):
    from .sources import normalized,PageText
    provider,tenant,job_id,api=info;data=json.loads(body)
    if job_id is None:
        items=data.get('jobs') if provider=='greenhouse' and isinstance(data,dict) else data
        if not isinstance(items,list):raise ValueError('Invalid ATS list')
        candidates=[]
        for item in items[:500]:
            if not isinstance(item,dict):continue
            raw=item.get('absolute_url') if provider=='greenhouse' else item.get('hostedUrl')
            try:url=normalized(raw)
            except (ValueError,TypeError):continue
            # Do not follow a returned posting into a different tenant/provider.
            target=endpoint(url)
            if not target or target[:2]!=info[:2] or target[2] is None:continue
            title=str(item.get('title') if provider=='greenhouse' else item.get('text') or '')
            candidates.append((title,url))
        candidates.sort(key=lambda x:0 if re.search(r'AI|data|machine learning|analytics|LLM|engineer',x[0],re.I) else 1)
        candidates=candidates[:30]
        total=data.get('meta',{}).get('total') if provider=='greenhouse' else None
        if not isinstance(total,int) or isinstance(total,bool) or total<0:total=None
        return {'structured_index':True,'text':'Public ATS job index: '+'; '.join(t for t,u in candidates),'links':[u for t,u in candidates],
                'ats_provider':provider,'ats_tenant':tenant,'api_url':api,'returned_count':len(items),'reported_total':total,'collection_scope':'Bounded sample, at most 30 links; not a complete vacancy census'}
    if not isinstance(data,dict) or str(data.get('id'))!=job_id:raise ValueError('ATS posting ID mismatch')
    if provider=='greenhouse':
        title=data.get('title','');location=(data.get('location') or {}).get('name','');content=html.unescape(data.get('content',''))
    else:
        title=data.get('text','');location=(data.get('categories') or {}).get('location','')
        content=data.get('descriptionPlain') or data.get('description','')
        content+=' '+data.get('additionalPlain','')
        for section in data.get('lists',[]):content+=' '+str(section.get('text',''))+' '+str(section.get('content',''))
    parser=PageText();parser.feed(content)
    text=' '.join(('Title: '+str(title)+' Location: '+str(location)+' '+' '.join(parser.parts)).split())[:18000]
    board_url=('https://job-boards.greenhouse.io/'+tenant) if provider=='greenhouse' else ('https://jobs.eu.lever.co/' if 'api.eu.lever.co' in api else 'https://jobs.lever.co/')+tenant
    return {'text':text,'links':[],'board_url':board_url,'structured_index':False,'ats_provider':provider,'ats_tenant':tenant,'ats_job_id':job_id,'api_url':api}
