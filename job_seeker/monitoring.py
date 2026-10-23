"""Deterministic monitoring policy and material opportunity changes."""
from decimal import Decimal

MATERIAL=('title','company','kind','fit','location','language','eligibility','mandatory_conflicts','concerns','evidence_quote')
def change_kind(previous,current):
    if previous is None:return 'new'
    return 'changed' if any(previous.get(k)!=current.get(k) for k in MATERIAL) else 'unchanged'

def scheduled_cap(settings,budget):
    cap=min(settings.limits.run_usd,settings.monitoring.daily_run_usd)
    remaining=Decimal(str(budget['ceiling']))-Decimal(str(budget['reserved']))
    return cap if remaining>=Decimal(str(cap)) else None
