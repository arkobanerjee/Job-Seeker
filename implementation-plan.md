# Adaptive research implementation checklist

Implement and review these items in order. Keep one worker. Research spending
continues to use the existing ledger and approval gate.

- [x] 1. Shared controller foundation: typed research decisions, bounded query/link admission, medium/high reasoning policy, persisted-time stop checks, offline tests.
- [x] 2. Integrate the controller with the restartable runner: plan → search → inspect → replan, compact evidence memory, durable action progress, budget reservation, normal Telegram clarification/resume, actual stop reasons. Enable medium assessment/planning and bounded high escalation through editable configuration.
- [x] 3. Adapt vacancy research: role synonyms, location/skill coverage, careers and ATS navigation, stale/failed source recovery, separate vacancy/fit/eligibility assessments.
- [ ] 4. Add a dedicated company-discovery operation with independent bounded search/page settings, funding/expansion/product/deployment themes, six-month preference and optional older backfill.
- [ ] 5. Qualify company evidence: concrete event, identity, source/date, relevance and evidence-strength labels; retain weak/rejected leads with reasons outside the main queue.
- [ ] 6. Aggregate one company card with multiple evidence items; preserve decisions/notes, suppress repeated announcements, show momentum coverage and competitor uncertainty.
- [ ] 7. Show chronological actions, queries, selected pages, replanning explanations, failures and coverage gaps in the dashboard; distinguish limited runs from exhausted research.
- [ ] 8. Evaluate fixed failure cases and fresh searches in isolation against the current baseline; measure useful distinct leads, claim support, duplication, coverage, time and cost. Then deploy and verify the merged version.

## Current implementation scope

Items 1, 2 and 3 are implemented. Set `[adaptive] enabled=true` to opt in for
new discovery runs. Existing cloud configs without this section keep the previous
behavior. Do not enable scheduled adaptive research until isolated acceptance in
item 8. Monitoring continues to revisit saved sources without the planner.

The runner now uses typed planner decisions, batches search/page work, replans
from compact observed evidence, and saves admitted rounds before execution.
Planning and page assessment default to medium reasoning; a planner can request
at most two high-effort assessment batches. Planning/review/search calls share the
existing spending ledger and per-run limits. Anthropic retains its existing
provider path; these effort fields currently control OpenAI calls only.

Questions use the existing durable question store and Telegram delivery path.
Waiting for a candidate answer pauses the wall-clock allowance; resuming does
not reset execution time, round/call counters or spending reservations. Tool
calls already in flight can finish beyond a time boundary. Interrupted calls
retain uncertain charges; resuming is explicit. Invalid/truncated structured
responses stop with saved progress rather than entering an unchecked retry loop.

Chronological planning/search/page/round/stop records are saved in checkpoint and
result JSON. Dashboard presentation is item 7. Limits or stalled research report
partial status; model-finished research can complete with documented coverage
gaps. This step does not claim improved search quality before evaluation.

Proposed ceilings per operation: four rounds, ten searches, twenty-four fetched
pages, thirty-two total model calls, twenty minutes, two high-effort escalations.
These are ceilings rather than targets. A stop must preserve unfinished work.
The implementation must not conflate a reached search cap with an inability to
inspect already discovered pages: the runner should use the controller's action
admission independently and treat individual resource caps appropriately.


## Item 3: vacancy research

Adaptive planning includes editable `[vacancy]` role families and regions,
unqueried term hints, failed page status and recent per-page outcomes (including
closed postings and rejection reasons). These measure attempts, not proven recall.
The planner is instructed to vary role titles and source types, recover from
senior-only/stale/inaccessible results, and distinguish fit from availability and
unknown eligibility. Model decisions remain bounded; quality needs item 8.

Observed supported ATS postings/boards and same-host career links receive
navigation priority. Up to `navigation_links` observed navigation candidates per
page are queued automatically, within the same fetch allowance. Only twelve
ranked observed links enter an adaptive page assessment. URLs are not fabricated;
all normal source safety checks still apply. ATS index traversal and newly
observed career links count as progress so navigation can reach a posting before
the no-progress stop. Other page/search/model/spending caps still apply.
