"""User-approved identity and domain rules; no inferred ownership claims."""
from urllib.parse import urlsplit
from .ats import endpoint

def matches_domain(url,domains):
    host=urlsplit(url).hostname or ''
    return any(host==d or host.endswith('.'+d) for d in domains)

def qualify(url,profile,edges):
    if matches_domain(url,profile['official_domains']):return {'status':'configured_official_domain','basis':'User-configured company domain'}
    for origin,target in edges:
        if not matches_domain(origin,profile['official_domains']):continue
        a,b=endpoint(target),endpoint(url)
        if target==url or (a and b and a[:2]==b[:2] and a[2] is None):
            return {'status':'linked_from_official_domain','basis':origin,'observed_link':target}
    return {'status':'unverified','basis':'No configured official-domain evidence'}
