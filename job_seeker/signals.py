"""Public company signals are evidence-backed leads, never inferred vacancies."""
from datetime import date
from pydantic import BaseModel,Field
from typing import Literal

class Signal(BaseModel):
    company: str = Field(min_length=1,max_length=200)
    title: str = Field(min_length=5,max_length=250)
    kind: Literal['company','hiring','technology','product','organization']
    source_id: str
    evidence_quote: str = Field(min_length=30,max_length=1500)
    relevance: str = Field(max_length=1000)
    event_date: str | None = Field(default=None,description='ISO date only when explicitly present in supplied text; otherwise null. Never use retrieval date as event date.')

def validate_signals(signals,page,run_id):
    good=[];bad=[];text=' '.join(page.get('text','').split()).casefold()
    for signal in signals:
        reason=None
        if page.get('http_status')!=200 or signal.source_id!=page.get('source_id'):reason='No matching retrieved source'
        elif ' '.join(signal.evidence_quote.split()).casefold() not in text:reason='Quote absent from source'
        elif signal.company.casefold() not in text:reason='Company absent from source'
        if reason:
            bad.append({'title':signal.title,'reason':reason});continue
        event_date=signal.event_date
        if event_date:
            try:date.fromisoformat(event_date)
            except ValueError:event_date=None
            if event_date and event_date not in page['text']:event_date=None
        good.append({**signal.model_dump(),'event_date':event_date,'url':page['url'],'observed_at':page.get('observed_at'),'run_id':run_id,
            'classification':'Company signal; no matching vacancy established','verification':'Quote and company text checked; signal interpretation and source ownership require review'})
    return good,bad

def query_plan(settings,offset=0,reserved=0):
    limit=max(1,settings.limits.max_searches-reserved)
    signals=settings.signals
    count=min(signals.max_queries,len(signals.queries),max(0,limit-1)) if signals.enabled else 0
    plan=[q.model_dump()|{'route':'vacancy'} for q in settings.search.queries[:limit-count]]
    for i in range(count):plan.append(signals.queries[(offset+i)%len(signals.queries)].model_dump())
    return plan[:limit],count
