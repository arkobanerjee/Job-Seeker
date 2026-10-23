"""Evidence-constrained competitor leads and bounded search expansion."""
from pydantic import BaseModel,Field

class CompetitorLead(BaseModel):
    seed_company: str = Field(min_length=1,max_length=200)
    company: str = Field(min_length=1,max_length=200)
    evidence_quote: str = Field(min_length=30,max_length=1500)
    source_id: str

def validate_leads(leads,page,known_companies,run_id):
    text=' '.join(page.get('text','').split()).casefold();known={c.casefold() for c in known_companies};accepted=[]
    for lead in leads:
        if page.get('http_status')!=200 or lead.source_id!=page.get('source_id'):continue
        if lead.seed_company.casefold() not in known or lead.seed_company.casefold()==lead.company.casefold():continue
        quote=' '.join(lead.evidence_quote.split()).casefold()
        if quote not in text or lead.company.casefold() not in quote or lead.seed_company.casefold() not in quote:continue
        accepted.append({**lead.model_dump(),'url':page['url'],'run_id':run_id,'observed_at':page.get('observed_at'),'verification':'Names and quote checked; competitor interpretation requires review','status':'unqualified_company_lead'})
    return accepted

def lead_query(company):
    # Escape punctuation as data; a company name cannot add search operators.
    import re
    clean=' '.join(re.findall(r'[\w]+',company,flags=re.UNICODE))[:160]
    return '"'+clean+'" (AI OR data OR analytics) careers'
