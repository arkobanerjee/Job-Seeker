"""Observed board-count changes, not predictions about future hiring."""
from datetime import datetime,timezone

def summarize(observations):
    result={'status':'insufficient_history','interpretation':'Source activity only; no hiring probability or confirmed closure inferred'}
    rows=[]
    for row in observations:
        try:
            stamp=datetime.fromisoformat(row['observed_at'])
            if stamp.tzinfo is None:continue
            rows.append((stamp.astimezone(timezone.utc),row))
        except (ValueError,KeyError,TypeError):continue
    rows.sort(key=lambda r:r[0])
    if len(rows)<2:return result
    if rows[0][0].date()==rows[-1][0].date():return result
    latest=rows[-1][1]
    keys=('ats_provider','ats_tenant','api_url','sample_limit','collection_scope')
    if any(not latest.get(k) for k in ('ats_provider','ats_tenant','api_url','collection_scope')):
        return {**result,'status':'incomparable_history','reason':'Collection provenance missing'}
    signature=lambda row:tuple(row.get(k) for k in keys)
    start=len(rows)-1
    while start>0 and signature(rows[start-1][1])==signature(latest):start-=1
    first,last=rows[start][1],latest
    if rows[start][0].date()==rows[-1][0].date():
        return {**result,'status':'incomparable_history','reason':'Collection changed; need observations on two new dates'} if start else result
    metric='reported_total' if first.get('reported_total') is not None and last.get('reported_total') is not None else 'returned_count'
    a,b=first.get(metric),last.get(metric)
    if any(not isinstance(x,int) or isinstance(x,bool) or x<0 for x in (a,b)):return result
    result.update(status='observed',baseline_reset=bool(start),metric=metric,baseline=a,current=b,delta=b-a,from_date=first['observed_at'],to_date=last['observed_at'],scope='Provider-reported board total' if metric=='reported_total' else 'Bounded API sample; count is not total employer vacancies')
    return result
