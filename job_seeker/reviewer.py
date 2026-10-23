"""A separate-context check; model agreement is not proof of eligibility."""
from typing import Literal
from pydantic import BaseModel,Field

class Review(BaseModel):
    verdict: Literal['accept','manual_review','reject']
    reason: str = Field(max_length=1200)
    blocker_quotes: list[str] = Field(default_factory=list,max_length=5)

def apply_review(finding,review,page):
    result=dict(finding)
    text=' '.join(page.get('text','').split()).casefold()
    quotes=[q for q in review.blocker_quotes if len(q)>=15 and ' '.join(q.split()).casefold() in text]
    verdict=review.verdict
    if verdict=='reject' and not quotes:verdict='manual_review'
    result['independent_review']={'verdict':verdict,'reason':review.reason,'blocker_quotes':quotes}
    result['review_status']='reviewed' if verdict=='accept' else 'needs_review' if verdict=='manual_review' else 'rejected'
    if verdict=='reject':
        result.update(kind='excluded',fit='conflict')
        result['rejection_reasons']=list(result.get('rejection_reasons',[]))+[review.reason]
        result['rejection_evidence']=list(result.get('rejection_evidence',[]))+quotes
    return result
