# Adaptive research implementation checklist

Implement and review these items in order. Keep one worker. Research spending
continues to use the existing ledger and approval gate.

- [x] 1. Shared controller foundation: typed research decisions, bounded query/link admission, medium/high reasoning policy, persisted-time stop checks, offline tests.
- [x] 2. Integrate the controller with the restartable runner: plan → search → inspect → replan, compact evidence memory, durable action progress, budget reservation, normal Telegram clarification/resume, actual stop reasons. Enable medium assessment/planning and bounded high escalation through editable configuration.
- [x] 3. Adapt vacancy research: role synonyms, location/skill coverage, careers and ATS navigation, stale/failed source recovery, separate vacancy/fit/eligibility assessments.
- [x] 4. Add a dedicated company-discovery operation with independent bounded search/page settings, funding/expansion/product/deployment themes, six-month preference and optional older backfill.
- [x] 5. Qualify company evidence: concrete event, identity, source/date, relevance and evidence-strength labels; retain weak/rejected leads with reasons outside the main queue.
- [x] 6. Aggregate one company card with multiple evidence items; preserve decisions/notes, suppress repeated announcements, show momentum coverage and competitor uncertainty.
- [ ] 7. Show chronological actions, queries, selected pages, replanning explanations, failures and coverage gaps in the dashboard; distinguish limited runs from exhausted research.
- [ ] 8. Evaluate fixed failure cases and fresh searches in isolation against the current baseline; measure useful distinct leads, claim support, duplication, coverage, time and cost. Then deploy and verify the merged version.

## Current implementation scope

Items 1–6 are implemented. Set `[adaptive] enabled=true` to opt in for
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


## Item 4: dedicated company operation

Manual `company` mode runs through the same serialized worker and spending
ledger, with independent `[company_discovery]` search/page/model ceilings. Its
run reservation is the lesser of the general and company run-dollar ceilings.
It does not borrow an active vacancy run's remaining pages or reset any budget.
Defaults: ten searches, twenty-four pages, thirty-two model calls, $0.25 ceiling.
It enables the adaptive path for this explicit operation; ordinary vacancy
settings and scheduled monitoring remain unchanged.

The five editable themes are funding, expansion, product, deployment and team.
Pending seed themes are admitted before discretionary refinement, subject to all
limits; short runs may still leave themes unattempted. The planner can ask first.
A minimum three stalled-round threshold permits refinement after theme batches.
The six-calendar-month default uses an `after:` query hint anchored to run start;
`include_older=true` omits it. This is not a guaranteed date filter or historical
census. Source event-date verification is still required.

Company runs retain signals in the existing registry/company queue and suppress
vacancy findings. UI button, workflow dispatch mode and local/cloud CLI are
connected. Resumption uses the saved company configuration/mode. Evidence-strength
qualification and multi-evidence cards remain items 5 and 6. No live research or
scheduled company job has been started for this implementation step.


## Item 5: evidence qualification

New signal output identifies an event type and skill/product terms copied from
source and supplied background. Existing exact quote/source checks remain the
first gate. Supported records receive `qualified` only when the quote names the
company, contains event-category wording, has no flagged negation/speculation,
and a profile term appears in both background and source with a relevance
explanation. Generic, uncertain or unmatched records remain `investigate` with
reasons. These conservative lexical checks do not establish all claim semantics,
publisher ownership, independent corroboration or a suitable vacancy. False
positives and false negatives still require the item 8 quality evaluation.

Labels distinguish reported funding, reported business expansion, explicit
hiring/team growth, relevant product launches and relevant deployments. Candidate
relevance remains an assessment. Missing/unchecked dates display Unknown.
Source ownership remains explicitly unverified at this gate.

Quote/source failures are retained in a durable rejected-signals registry table
with company, URL, quote, run and rejection reason. The dashboard main queue shows
qualified signals; a collapsed investigation section retains weak, rejected,
competitor and board-activity leads. Historical unclassified signals are not
silently promoted. Existing stable decision IDs are preserved. For same-source
collisions the qualified record takes precedence; full evidence aggregation is
still item 6. Historical signals are not reprocessed through paid calls here.


## Item 6: company evidence aggregation and decision continuity

One stable card now represents a normalized company name, across signal,
competitor, rejected-evidence and momentum routes. Configured aliases merge only
when the registry identifies them as user-configured; different names are not
merged by shared hosting, ATS domain or inferred similarity. Unidentified board
activity remains separated by source URL. Name-based identity is labelled as
unverified, not independent company-identity verification.

Cards retain all evidence groups with status, label, quote, event date, source
URLs, observation times, run references and uncertainty. Matching excerpts with
matching evidence type/status/label/date are grouped as copies; all receipts
remain inspectable. Tracking-only URL parameters are ignored for source counts.
Different excerpts remain separate even if they might describe the same event;
there is no speculative semantic deduplication or independent-source count claim.
Momentum observations preserve their distinct observation periods.

The card ID is independent of source additions, quotations and event labels.
Prior per-source IDs remain readable/writable through the API. Earlier grouped
alias IDs are also checked. Current company decisions take precedence; otherwise
the most recent earlier decision is used. Every earlier note/status is exposed
in preserved history rather than concatenated, overwritten or deleted. A newly
saved company note does not erase old records. Dismissed companies remain in the
collapsed review section when new evidence arrives.

Validation covers evidence copies, multiple labels, shared-host non-merging,
configured aliases, historical-ID migration, note preservation and actual page
rendering of evidence/history/dismissed cards. No live deployment or paid research
was performed. Chronological research trace UI is item 7; full comparison and
production acceptance remain item 8.
