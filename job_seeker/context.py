"""Bounded page excerpts; retain complete observed URLs rather than cutting them."""
from urllib.parse import urlsplit


def application_form(page):
    return 'apply' in urlsplit(page.get('url','')).path.casefold().rstrip('/').split('/')


def title_only(page,title,company):
    norm=lambda value:' '.join(value.split()).casefold().strip()
    return norm(page.get('text','')) in {norm(title),norm(title+' @ '+company)}


def compact_page(page,rank=lambda url:0):
    text=page.get('text') or ''
    raw=text.encode('utf-8')
    excerpt=raw[:14000].decode('utf-8',errors='ignore')
    links=[];used=0
    for url in sorted(dict.fromkeys(page.get('links') or []),key=rank):
        size=len(url.encode('utf-8'))+8
        if len(links)<12 and used+size<=4000:
            links.append(url);used+=size
    return {**{k:page.get(k) for k in ('url','source_id','closed_marker')},'text':excerpt,'links':links,
            'context_omissions':{'text_bytes':len(raw)-len(excerpt.encode('utf-8')),'links':len(page.get('links') or [])-len(links)}}
