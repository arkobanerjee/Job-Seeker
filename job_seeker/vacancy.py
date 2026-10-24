"""Vacancy search guidance and ranking over observed URLs only."""
import re
from urllib.parse import urlsplit
from .ats import endpoint

VACANCY_GUIDANCE = """VACANCY RESEARCH:
Use candidate facts and editable role/region preferences. Cover both role tracks
and prioritize Germany; broaden to other allowed regions when useful. Vary role
synonyms, skills and source types across rounds rather than appending synonyms to
one oversized query. Mix unrestricted employer searches with public ATS queries.
Query coverage records attempts, not exhaustive coverage or successful retrieval.
If results are mainly senior roles, try junior/early-career or adjacent titles.
If pages are closed or inaccessible, change query/source and inspect an observed
careers page or board. Do not retry the same failed URL in this run. A board or
careers index is discovery evidence; inspect individual postings before assessing.
Separate listing availability, technical fit, mandatory conflicts and unknown
language/authorization facts. An English advert does not prove English-only work;
missing sponsorship does not prove ineligibility. Preserve relevant conflicts for
manual review. A source title/path/rank is a navigation hint, never vacancy proof.
"""


def navigation_rank(url):
    info = endpoint(url)
    if info: return 0 if info[2] is not None else 1
    path = urlsplit(url).path.casefold()
    if re.search(r'/(jobs?|careers?|vacancies|stellenangebote|karriere)(/|$)',path): return 2
    if re.search(r'/(privacy|terms|login|signin|about|contact)(/|$)',path): return 9
    return 5


def navigation_candidates(page, maximum):
    origin = urlsplit(page['url']).hostname
    links = dict.fromkeys(page.get('links',[]))
    candidates = [u for u in links if navigation_rank(u)<5 and
                  (urlsplit(u).hostname==origin or endpoint(u))]
    return sorted(candidates,key=navigation_rank)[:maximum]


def coverage_memory(settings,state):
    text = ' '.join(state.get('attempted_queries',[])).casefold()
    def mentioned(term):
        return bool(re.search(r'(?<!\w)'+re.escape(term.casefold())+r'(?!\w)',text))
    return {
        'role_families':settings.vacancy.role_families,
        'regions':settings.vacancy.regions,
        'role_terms_not_yet_queried':{k:[t for t in terms if not mentioned(t)] for k,terms in settings.vacancy.role_families.items()},
        'regions_not_yet_queried':[t for t in settings.vacancy.regions if not mentioned(t)],
        'recent_page_outcomes':state.get('vacancy_outcomes',[])[-16:],
        'failed_pages':[{'url':u,'status':p.get('http_status'),'error':p.get('error')} for u,p in state.get('sources',{}).items() if p.get('http_status')!=200][-12:],
        'note':'Query terms measure attempted searches only; relevance and availability require posting evidence.'}
