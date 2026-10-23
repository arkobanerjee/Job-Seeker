"""Observed board-count changes, not predictions about future hiring."""
from datetime import datetime

def summarize(observations):
    rows=sorted([r for r in observations if r.get('observed_at')],key=lambda r:r['observed_at'])
    result={'status':'insufficient_history','interpretation':'Source activity only; no hiring probability or confirmed closure inferred'}
    if len(rows)<2:return result
    first,last=rows[0],rows[-1]
    try:
        if datetime.fromisoformat(first['observed_at']).date()==datetime.fromisoformat(last['observed_at']).date():return result
    except ValueError:return result
    metric='reported_total' if first.get('reported_total') is not None and last.get('reported_total') is not None else 'returned_count'
    a,b=first.get(metric),last.get(metric)
    if a is None or b is None:return result
    result.update(status='observed',metric=metric,baseline=a,current=b,delta=b-a,from_date=first['observed_at'],to_date=last['observed_at'],scope='Provider-reported board total' if metric=='reported_total' else 'Bounded API sample; count is not total employer vacancies')
    return result
