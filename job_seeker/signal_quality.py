"""Conservative evidence gates, separate from model-assessed candidate relevance."""
import re

EVENTS={
    'funding':('Reported funding',r'\b(raised|secured|funding|financing|investment|series [abc])\b'),
    'expansion':('Reported business expansion',r'\b(expand\w*|new office|opened|opening|new market)\b'),
    'hiring':('Explicit hiring / team growth',r'\b(hiring|recruiting|growing our team|expand\w* team|team expansion)\b'),
    'product':('Relevant product launch',r'\b(launch\w*|released?|introduc\w*|general availability)\b'),
    'deployment':('Relevant deployment / case study',r'\b(deploy\w*|production|implemented|case study)\b'),
}


def qualify_signal(signal,page,background):
    quote=' '.join(signal.evidence_quote.split()).casefold()
    source=' '.join(page.get('text','').split()).casefold()
    profile=' '.join(background.split()).casefold()
    reasons=[]
    if not re.search(r'(?<!\w)'+re.escape(' '.join(signal.company.split()).casefold())+r'(?!\w)',quote):
        reasons.append('Evidence excerpt does not identify the company as the event subject')
    event=EVENTS.get(signal.event_type)
    if not event: reasons.append('No concrete qualifying event; technical interest or generic mention only')
    elif not re.search(event[1],quote): reasons.append('Event category lacks matching wording in the quoted evidence')
    if re.search(r'\b(no|not|never|rumou?r|unconfirmed|hypothetical|might|could)\b',quote):
        reasons.append('Excerpt contains negation, speculation or uncertainty; investigate manually')
    def contains(term,text):
        return bool(re.search(r'(?<!\w)'+re.escape(term.casefold().strip())+r'(?!\w)',text))
    matched=[t for t in signal.profile_terms if len(t.strip())>=2 and contains(t,source) and contains(t,profile)]
    if not matched: reasons.append('No supplied profile term was found in both background and source')
    if len(signal.relevance.strip())<20: reasons.append('Candidate relevance needs a specific explanation')
    return {'qualification_status':'investigate' if reasons else 'qualified',
            'evidence_strength':event[0] if event else 'Technical interest / company to investigate',
            'qualification_reasons':reasons,
            'matched_profile_terms':matched,
            'source_ownership':'unverified',
            'qualification_version':1,
            'qualification_note':'Exact quote and conservative wording checks passed; event interpretation and candidate relevance remain assessments. No suitable vacancy or independent corroboration established.'}
