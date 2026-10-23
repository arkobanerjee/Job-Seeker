"""Bounded public ATS count observations. No search, model or paid ledger calls."""
from datetime import datetime,timezone
from urllib.parse import urlsplit
from .ats import endpoint
from .sources import SourceTools,normalized


def board_targets(registry,seeds,limit):
    rows=[];sources=registry.export()['sources']
    for raw in [*seeds,*[s['url'] for s in sources]]:
        try:
            url=normalized(raw);info=endpoint(url)
        except (ValueError,TypeError):continue
        if not info:continue
        board='https://'+('job-boards.greenhouse.io' if info[0]=='greenhouse' else urlsplit(url).netloc)+'/'+info[1]
        if board not in rows:rows.append(board)
    last={s['url']:max((h.get('observed_at') or '' for h in s.get('history',[])),default='') for s in sources}
    return sorted(rows,key=lambda u:last.get(u,''))[:limit]


def observe(registry,run_id,seeds=(),limit=4):
    targets=board_targets(registry,seeds,limit)
    tools=SourceTools(None,lambda:None,max_fetches=limit);tools.allowed.update(targets)
    counts=[]
    for url in targets:
        page=tools.fetch(url)
        registry.ingest(run_id,[],{url:page})
        counts.append({'url':url,'http_status':page.get('http_status'),'count_observed':bool(page.get('http_status')==200 and page.get('structured_index'))})
    return {'run_id':run_id,'status':'completed','mode':'board_observations','observed_at':datetime.now(timezone.utc).isoformat(),'targets':counts,'searches':0,'model_calls':0,'fetches':tools.fetches,'findings':[], 'sources':tools.records}
