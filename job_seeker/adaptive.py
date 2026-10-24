"""Provider-independent decisions and deterministic limits for adaptive research.

This module performs no network calls. The runner must reserve paid calls and
checkpoint decisions before executing actions. Web content is evidence only.
"""
from datetime import datetime, timezone
from typing import Literal
from pydantic import Field
from .settings import Strict, Query, AdaptiveSettings


class ResearchDecision(Strict):
    action: Literal['research', 'finish', 'ask_user']
    explanation: str = Field(min_length=1, max_length=1200)
    queries: list[Query] = Field(default_factory=list, max_length=5)
    inspect_urls: list[str] = Field(default_factory=list, max_length=10)
    coverage_gaps: list[str] = Field(default_factory=list, max_length=8)
    question: str = Field(default='', max_length=1500)
    use_high_reasoning: bool = False


def stop_reason(state, policy, limits, now=None):
    """Use a persisted UTC deadline origin, so resuming cannot reset the clock."""
    now = now or datetime.now(timezone.utc)
    started = datetime.fromisoformat(state['started_at'])
    if started.tzinfo is None:
        raise ValueError('Research start must include a timezone')
    if (now-started).total_seconds()-state.get('paused_seconds',0) >= policy.max_minutes*60:
        return 'time_limit'
    for key, cap, reason in (
        ('rounds', policy.max_rounds, 'round_limit'),
        ('model_calls', limits.max_model_calls, 'model_call_limit'),
        ('stalled_rounds', policy.max_stalled_rounds, 'no_progress'),
    ):
        if state.get(key, 0) >= cap:
            return reason
    if state.get('searches', 0) >= limits.max_searches and state.get('fetches', 0) >= limits.max_pages:
        return 'research_resources_exhausted'
    return None


def admitted_actions(decision, state, policy, limits, observed_urls):
    """Admit only novel queries and observed unread URLs, under remaining caps.

    Budget authorization, URL safety checks and candidate-question persistence
    remain mandatory runner boundaries. Model requests cannot override them.
    """
    if decision.action != 'research':
        return {'queries': [], 'inspect_urls': [], 'high_reasoning': False}
    seen = {' '.join(q.split()).casefold() for q in state.get('attempted_queries', [])}
    queries = []
    capacity = min(policy.queries_per_round, max(0, limits.max_searches-state.get('searches', 0)))
    for query in decision.queries:
        key = ' '.join(query.query.split()).casefold()
        if key not in seen and len(queries) < capacity:
            seen.add(key)
            queries.append(query.model_dump())
    allowed = set(observed_urls) - set(state.get('pages_done', []))
    urls = []
    capacity = min(policy.pages_per_round, max(0, limits.max_pages-state.get('fetches', 0)))
    for url in decision.inspect_urls:
        if url in allowed and url not in urls and len(urls) < capacity:
            urls.append(url)
    return {'queries': queries, 'inspect_urls': urls,
            'high_reasoning': decision.use_high_reasoning and state.get('high_escalations', 0) < policy.max_high_escalations}


def research_loop(state, policy, limits, *, plan, search, inspect, ask, persist, check):
    """Checkpoint a round before execution; resume its saved actions, not its plan.

    Tool callbacks keep their own durable counters/reservations. A process death
    during a tool may leave an uncertain charge, which this loop never refunds.
    """
    state.setdefault('research_trace', [])
    def trace(kind, **data):
        state['research_trace'].append({'at':datetime.now(timezone.utc).isoformat(), 'type':kind, **data})
        persist()
    def stop(reason):
        state['stop_reason'] = reason
        trace('stop', reason=reason)
    while True:
        check()
        active = state.get('active_round')
        # The admitted last round can finish after incrementing rounds.
        snapshot = dict(state)
        if active: snapshot['rounds'] = max(0, state.get('rounds', 0)-1)
        reason = stop_reason(snapshot, policy, limits)
        if reason:
            stop(reason); return
        if not active:
            decision = plan()
            observed = [x['url'] for x in state.get('queue', [])]
            actions = admitted_actions(decision, state, policy, limits, observed)
            state['rounds'] = state.get('rounds', 0)+1
            active = {'decision':decision.model_dump(), 'actions':actions, 'query_index':0,
                      'phase':'search', 'inspected':0,
                      'before':len(state.get('findings', []))+len(state.get('signals', [])),
                      'navigation_before':state.get('navigation_progress',0)}
            state['active_round'] = active
            if actions['high_reasoning']:
                state['high_escalations'] = state.get('high_escalations', 0)+1
            trace('plan', round=state['rounds'], decision=decision.model_dump(), admitted=actions)
        decision = ResearchDecision.model_validate(active['decision'])
        if decision.action == 'finish':
            state.pop('active_round', None); stop('model_finished'); return
        if decision.action == 'ask_user':
            if not decision.question.strip():
                raise ValueError('Planner requested clarification without a question')
            if not ask(decision): return
            state.pop('active_round', None); persist(); continue
        actions = active['actions']
        while active['query_index'] < len(actions['queries']):
            check()
            query = actions['queries'][active['query_index']]
            # Persist intent before calling; SourceTools checkpoints charged work.
            state.setdefault('attempted_queries', [])
            if query['query'] not in state['attempted_queries']:
                state['attempted_queries'].append(query['query'])
            trace('search_start', query=query['query'])
            receipt=search(query)
            active['query_index'] += 1
            trace('search_end', query=query['query'], **(receipt or {}))
        active['phase'] = 'inspect'; persist()
        inspect(actions['inspect_urls'], actions['high_reasoning'])
        if state.get('status') == 'waiting_user': return
        after = len(state.get('findings', []))+len(state.get('signals', []))
        progressed = after > active['before'] or state.get('navigation_progress',0)>active.get('navigation_before',0)
        state['stalled_rounds'] = state.get('stalled_rounds', 0)+1 if not progressed else 0
        trace('round_end', round=state['rounds'], inspected=active['inspected'], new_records=after-active['before'])
        state.pop('active_round', None); persist()
