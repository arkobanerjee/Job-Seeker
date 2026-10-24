"""Dedicated company research configuration and bounded theme coverage."""
import calendar
from datetime import datetime
from urllib.parse import urlsplit
import re
from .adaptive import ResearchDecision

TERMS = {
    'funding':'company funding investment announcement',
    'expansion':'company expansion new office engineering team',
    'product':'company launches product platform announcement',
    'deployment':'engineering blog customer case study production deployment',
    'team':'company growing hiring data AI team announcement',
}

COMPANY_GUIDANCE = """COMPANY DISCOVERY OPERATION:
Find concrete funding, expansion, product launches, deployments and team-growth
events relevant to the candidate. Inspect original announcements and company
pages. A generic blog, author biography or keyword mention is insufficient.
Identify the company and event; quote evidence and distinguish facts from
inferred candidate relevance. Funding or a product launch does not establish
hiring or a suitable vacancy. Competitor relationships alone do not establish
growth. Retain true event dates separately from retrieval dates; undated stays
unknown. Search date operators are hints, not verified publication-date filters.
After theme seed queries, refine based on results, verify identity/claims and
follow observed relevant article/product/company links. No minimum card quota.
Return company signals, not vacancy findings. Explain remaining coverage gaps.
Never refine into personal vacancy searches or ATS posting queries. Keep funding,
expansion, products and deployments as the search objective. Quote an excerpt
containing the company name AND the concrete event wording. Prefer source event
pages over careers navigation. A feature list does not establish a product launch.
"""


def operation_settings(settings,operation):
    if operation not in ('discovery','company'):raise ValueError('Unknown research operation')
    settings = settings.model_copy(deep=True)
    if operation=='company':
        c=settings.company_discovery
        settings.limits.run_usd=min(settings.limits.run_usd,c.run_usd)
        settings.limits.max_searches=c.max_searches
        settings.limits.max_pages=c.max_pages
        settings.limits.max_model_calls=c.max_model_calls
        settings.adaptive.enabled=True
        # Leave room for a refinement round after the five initial themes.
        settings.adaptive.max_stalled_rounds=max(3,settings.adaptive.max_stalled_rounds)
        settings.monitoring.enabled=False
        settings.signals.enabled=True
        settings.competitors.enabled=False
    if settings.adaptive.enabled and not settings.monitoring.enabled:
        settings.model.max_output_tokens=settings.adaptive.max_output_tokens
    return settings


def company_rank(url):
    return 0 if re.search(r'/(blog|news|press|announcements|products?|customers?|case-studies)(/|$)',urlsplit(url).path,re.I) else 5


def seed_queries(settings,started_at):
    c=settings.company_discovery
    now=datetime.fromisoformat(started_at)
    month_index=now.year*12+now.month-1-c.lookback_months
    year,month=divmod(month_index,12);month+=1
    lower=now.replace(year=year,month=month,day=min(now.day,calendar.monthrange(year,month)[1])).date().isoformat()
    suffix='' if c.include_older else ' after:'+lower
    return [{'theme':t,'track':'ai','query':c.focus+' '+TERMS[t]+suffix} for t in dict.fromkeys(c.themes)]


def company_memory(settings,state):
    seeds=seed_queries(settings,state['started_at'])
    attempted=set(state.get('attempted_queries',[]))
    return {'theme_seeds':seeds,'themes_not_attempted':[s['theme'] for s in seeds if s['query'] not in attempted],
            'lookback_months':settings.company_discovery.lookback_months,
            'include_older':settings.company_discovery.include_older,
            'note':'Attempted themes are not exhaustive coverage; date hints require source verification.'}


def cover_themes(decision,settings,state):
    if decision.action=='ask_user':return decision
    kept=[q for q in decision.queries if not re.search(r'\b(vacanc\w*|careers?|job postings?|job openings?|individual jobs?)\b|site:(?:jobs\.|job-boards\.|boards\.greenhouse)',q.query,re.I)]
    if len(kept)!=len(decision.queries):
        decision=decision.model_copy(update={'queries':kept,'coverage_gaps':(decision.coverage_gaps+['Vacancy-focused query omitted in company mode'])[:8]})
    pending=[s for s in seed_queries(settings,state['started_at']) if s['query'] not in state.get('attempted_queries',[])]
    capacity=min(settings.adaptive.queries_per_round,settings.limits.max_searches-state.get('searches',0))
    if not pending or capacity<=0:return decision
    return ResearchDecision(action='research',explanation='Cover unattempted company themes before refinement. '+decision.explanation[:900],
        queries=[{'track':s['track'],'query':s['query']} for s in pending[:capacity]],
        inspect_urls=decision.inspect_urls,coverage_gaps=decision.coverage_gaps,use_high_reasoning=decision.use_high_reasoning)
