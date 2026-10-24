# Adaptive research implementation checklist

Implement and review these items in order. Keep one worker. Research spending
continues to use the existing ledger and approval gate.

- [x] 1. Shared controller foundation: typed research decisions, bounded query/link admission, medium/high reasoning policy, persisted-time stop checks, offline tests.
- [ ] 2. Integrate the controller with the restartable runner: plan → search → inspect → replan, compact evidence memory, durable action progress, budget reservation, normal Telegram clarification/resume, actual stop reasons. Enable medium assessment/planning and bounded high escalation through editable configuration.
- [ ] 3. Adapt vacancy research: role synonyms, location/skill coverage, careers and ATS navigation, stale/failed source recovery, separate vacancy/fit/eligibility assessments.
- [ ] 4. Add a dedicated company-discovery operation with independent bounded search/page settings, funding/expansion/product/deployment themes, six-month preference and optional older backfill.
- [ ] 5. Qualify company evidence: concrete event, identity, source/date, relevance and evidence-strength labels; retain weak/rejected leads with reasons outside the main queue.
- [ ] 6. Aggregate one company card with multiple evidence items; preserve decisions/notes, suppress repeated announcements, show momentum coverage and competitor uncertainty.
- [ ] 7. Show chronological actions, queries, selected pages, replanning explanations, failures and coverage gaps in the dashboard; distinguish limited runs from exhausted research.
- [ ] 8. Evaluate fixed failure cases and fresh searches in isolation against the current baseline; measure useful distinct leads, claim support, duplication, coverage, time and cost. Then deploy and verify the merged version.

## Item 1 scope

`job_seeker/adaptive.py` is a network-free foundation. It is deliberately not yet
wired into production, so existing runs and configuration remain compatible.
Runner integration is item 2; no claim of adaptive production behavior is made
until that integration and its restart/budget tests pass.

Proposed ceilings per operation: four rounds, ten searches, twenty-four fetched
pages, thirty-two total model calls, twenty minutes, two high-effort escalations.
These are ceilings rather than targets. A stop must preserve unfinished work.
The implementation must not conflate a reached search cap with an inability to
inspect already discovered pages: the runner should use the controller's action
admission independently and treat individual resource caps appropriately.
