"""Cross-source claim review; different hosts alone do not prove independence."""
import hashlib,json
from urllib.parse import urlsplit
from typing import Literal
from pydantic import BaseModel,Field

class CorroborationReview(BaseModel):
    verdict: Literal['supports_same_claim','contradicts','unrelated','insufficient']
    reason: str = Field(max_length=1200)
    quote_a: str = Field(max_length=1500)
    quote_b: str = Field(max_length=1500)

def candidate_pairs(signals):
    pairs=[];seen=set()
    for i,a in enumerate(signals):
        for b in signals[i+1:]:
            if a['company'].casefold()!=b['company'].casefold() or a['kind']!=b['kind']:continue
            if urlsplit(a['url']).hostname==urlsplit(b['url']).hostname:continue
            if ' '.join(a['evidence_quote'].split()).casefold()==' '.join(b['evidence_quote'].split()).casefold():continue
            ordered=sorted([a,b],key=lambda x:(x['url'],x['evidence_quote']))
            data=[{k:s.get(k) for k in ('company','kind','url','evidence_quote','event_date')} for s in ordered]
            ident=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()[:24]
            if ident not in seen:seen.add(ident);pairs.append((ident,data))
    return pairs

def checked_result(ident,pair,review,publishers):
    def publisher(url):
        host=urlsplit(url).hostname or ''
        matches=[name for name,domains in publishers.items() if any(host==d or host.endswith('.'+d) for d in domains)]
        return matches[0] if len(matches)==1 else None
    verdict=review.verdict
    def present(quote,source):return len(quote)>=30 and ' '.join(quote.split()).casefold() in ' '.join(source.split()).casefold()
    if verdict in ('supports_same_claim','contradicts') and not (present(review.quote_a,pair[0]['evidence_quote']) and present(review.quote_b,pair[1]['evidence_quote'])):verdict='insufficient'
    a,b=publisher(pair[0]['url']),publisher(pair[1]['url'])
    independence='configured_distinct_publishers' if a and b and a!=b else 'same_configured_publisher' if a and a==b else 'publisher_independence_unverified'
    return {'id':ident,'company':pair[0]['company'],'kind':pair[0]['kind'],'sources':pair,'verdict':verdict,'reason':review.reason,'independence':independence,'qualification':'Cross-source model review; not a verified vacancy or legal eligibility determination'}
