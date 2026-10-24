import unittest
from datetime import datetime, timezone
from pydantic import ValidationError
from job_seeker.adaptive import AdaptiveSettings, ResearchDecision, admitted_actions, stop_reason
from job_seeker.settings import Limits


class AdaptiveTests(unittest.TestCase):
    def test_novel_queries_observed_links_and_remaining_capacity(self):
        decision = ResearchDecision(action='research', explanation='Try another title',
            queries=[{'track':'ai','query':q} for q in [' RAG  Germany ', 'ML Germany', 'ml germany', 'AI Europe']],
            inspect_urls=['https://invented.example', 'https://known.example', 'https://known.example'],
            use_high_reasoning=True)
        state = {'attempted_queries':['rag germany'], 'searches':5, 'fetches':11, 'high_escalations':2}
        actions = admitted_actions(decision, state, AdaptiveSettings(), Limits(), ['https://known.example'])
        self.assertEqual([q['query'] for q in actions['queries']], ['ML Germany'])
        self.assertEqual(actions['inspect_urls'], ['https://known.example'])
        self.assertFalse(actions['high_reasoning'])

    def test_resume_keeps_original_deadline(self):
        state = {'started_at':'2026-10-24T08:00:00+00:00'}
        self.assertEqual(stop_reason(state, AdaptiveSettings(), Limits(), datetime(2026,10,24,8,21,tzinfo=timezone.utc)), 'time_limit')
        state['paused_seconds'] = 120
        self.assertIsNone(stop_reason(state, AdaptiveSettings(), Limits(), datetime(2026,10,24,8,21,tzinfo=timezone.utc)))

    def test_each_stop_boundary(self):
        now = datetime(2026,10,24,8,0,tzinfo=timezone.utc)
        for key,value,reason in [('rounds',4,'round_limit'), ('model_calls',16,'model_call_limit'), ('stalled_rounds',2,'no_progress')]:
            self.assertEqual(stop_reason({'started_at':now.isoformat(),key:value},AdaptiveSettings(),Limits(),now), reason)
        state = {'started_at':now.isoformat(), 'searches':6}
        self.assertIsNone(stop_reason(state,AdaptiveSettings(),Limits(),now))
        state['fetches'] = 12
        self.assertEqual(stop_reason(state,AdaptiveSettings(),Limits(),now), 'research_resources_exhausted')
        state.update(sources={'https://example.com/last':{}},queue=[{'url':'https://example.com/last'}],pages_done=[])
        self.assertIsNone(stop_reason(state,AdaptiveSettings(),Limits(),now))
        state['pages_done']=['https://example.com/last']
        self.assertEqual(stop_reason(state,AdaptiveSettings(),Limits(),now),'research_resources_exhausted')

    def test_finish_cannot_smuggle_actions(self):
        decision = ResearchDecision(action='finish', explanation='Enough evidence', queries=[{'track':'ai','query':'extra'}])
        self.assertEqual(admitted_actions(decision,{},AdaptiveSettings(),Limits(),[])['queries'], [])

    def test_invalid_and_unbounded_decisions_rejected(self):
        with self.assertRaises(ValidationError):
            ResearchDecision(action='shell', explanation='Run code')
        with self.assertRaises(ValidationError):
            AdaptiveSettings(max_rounds=100)
