"""Provider-independent decisions and deterministic limits for adaptive research.

This module performs no network calls. The runner must reserve paid calls and
checkpoint decisions before executing actions. Web content is evidence only.
"""
from datetime import datetime, timezone
from typing import Literal
from pydantic import Field
from .settings import Strict, Query


class AdaptiveSettings(Strict):
    enabled: bool = False
    max_rounds: int = Field(default=4, ge=1, le=8)
    queries_per_round: int = Field(default=3, ge=1, le=5)
    pages_per_round: int = Field(default=6, ge=1, le=10)
    max_minutes: int = Field(default=20, ge=1, le=20)
    max_stalled_rounds: int = Field(default=2, ge=1, le=4)
    planning_effort: Literal['medium', 'high'] = 'medium'
    assessment_effort: Literal['medium', 'high'] = 'medium'
    max_high_escalations: int = Field(default=2, ge=0, le=4)


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
    if (now-started).total_seconds() >= policy.max_minutes*60:
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
