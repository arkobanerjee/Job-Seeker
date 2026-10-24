# Single-worker versus multiple-worker comparison

Status: isolated local A/B runner and trace recorder implemented in experiments/comparison.py. Offline simulation verified; no paid comparison executed. The first runner uses two fixed subtasks, bounded follow-up links, identical validation and a shared review policy. Configuration C, multiple briefs/repeats and human-labelled quality scoring remain subsequent steps. This is separate from the deployed application.

## Objective and scope

Determine whether two research workers improve useful job discovery, speed or cost efficiency for the same candidate and resources. A worker is an independently contextualized researcher, not necessarily a separate machine. Keep the same bounded search/fetch/assessment behavior, tools, output contracts and reviewer policy as the application. Browser/code sandboxes are a separate experimental variable and are excluded from the initial comparison.

## Isolation contract

- Use a dedicated experiment entry point and private/comparison workspace. Never invoke production cloud run/bootstrap/sync/reserve functions.
- Store experiment catalog, registry, cache, questions, outbox, traces and budget ledger exclusively under that workspace. No production writes or shared SQLite connections.
- Use fresh equal starting snapshots for each configuration/repeat. Snapshot candidate background and configuration; record their hashes. Shared test fixtures are immutable.
- Disable schedules, Telegram messages, applications, outreach and production dashboard publishing. Use recorded clarification answers or a local review queue.
- Supply only model/search credentials to experiment workers. Do not inherit Cloudflare, GitHub deployment, dashboard or Telegram credentials.
- A coordinator owns the experiment ledger and final writes. Parallel workers return results to it; they do not become parallel production-state writers.
- Reuse application modules through an explicit workspace/tool interface. Any module hardcoded to production ROOT must be adapted before use. Copying a config alone does not establish isolation.

## Configurations

| ID | Researchers | Task handling | Purpose |
|---|---:|---|---|
| A | 1 | Execute fixed AI and data/analytics subtasks sequentially | Baseline |
| B | 2 | Execute the same subtasks concurrently in separate contexts | Parallelism and context separation |
| C | 2 | Same subtasks with shared coverage and bounded handoffs | Coordination benefit; disabled initially |

All configurations use the same final merge/deduplication and reviewer rules. Count every planner, reviewer, merger and coordinator model call in total cost. Keep model/provider/settings constant for the initial test. Test model changes separately.

## Budget

The comparison has a separate cumulative USD 5 ceiling, covering all arms, repeats, search costs and paid evaluation. This is a fresh experiment allowance; it does not reset or increase the production allowance. Initial private configuration: private/comparison/experiment.json.

Before running, calculate worst-case token/search reservations for the entire proposed batch. Start only a batch that fits the remaining experiment allowance. Reserve centrally before dispatch, including concurrent workers. Keep actual measured usage and conservative reservations separately. No automatic refunds, rollover or cap reset.

Suggested pilot: three briefs, two repeats each, A and B, for 12 total runs. A provisional USD 0.30 envelope per run leaves USD 1.40 for evaluation/contingency; validate feasibility first and reduce workload or repeats if needed. USD 0.30 is a proposed envelope, not a measured cost estimate. Every arm in a pair receives equal total resources. C requires a subsequent allocation within the remaining cap or an explicit new allowance.

## Inputs and fairness

Briefs: Germany applied AI/RAG roles; Germany data/analytics roles; English-language Europe/UAE/remote roles. Freeze candidate constraints, task divisions, model settings, starting state and acceptance rubric before running. Keep searches, pages and model token budgets equal in total across arms, not per worker. Split limited resources explicitly and record unused capacity.

For live tests, run paired arms close together and alternate order. Record capture times because postings and search ranking change. Reset caches equally; report warm-cache experiments separately. Never let an earlier arm populate a later arm's working memory.

## Trace contract

Append events with experiment_id, run_id, arm, repeat, worker_id, task_id, event_id, parent_event_id, UTC timestamp, duration, event_type, status, structured decision label, sanitized tool parameters, input/output references and hashes, error category, token usage, actual cost and reservation. Record tool start and completion/failure separately. Redact secrets and exclude candidate contact details from queries.

Record task assignments and handoffs, exact queries and result rankings, fetch attempts and snapshots, evidence extraction, classification, review changes, deduplication, clarifications, retries and stopping reasons. Link each final finding to evidence and the actions that discovered it. Existing reconstructed provenance paths are supporting evidence, not a complete chronological action log. Do not collect hidden chain-of-thought; evaluate observable actions and concise decision labels.

## Outcome metrics

| Metric | Definition |
|---|---|
| Useful yield | Unique open roles meeting the frozen fit rubric, with source evidence |
| Shortlist precision | Human-labelled relevant shortlisted roles / all shortlisted roles |
| Recall on frozen cases | Relevant labelled roles recovered / all relevant labelled roles in that set |
| Pooled discovery coverage | Relevant roles recovered / relevant roles in the reviewed union across arms; not web-wide recall |
| Rejection accuracy | Evidence-supported barrier decisions / reviewed barrier decisions |
| Unsupported claims | Unsupported material statements / reviewed material statements |
| Efficiency | Total measured cost / useful unique jobs; undefined when yield is zero, report cost and zero yield |
| Latency | Time to first useful job and total elapsed time; also summed worker time |
| Human burden | Clarification count, avoidable questions, review minutes and corrections |

Judge technical fit separately from language/location/authorization barriers. Keep suitable-but-blocked roles in the manual/apply-anyway queue. Unknown authorization remains unknown. Employer-stated requirements and candidate-provided claims are evidence, not legal eligibility determinations.

## Process metrics

- Query yield: new useful roles attributable to a query; specify first-discovery attribution and record later verification separately.
- Search overlap: intersection / union of canonical job IDs or URLs; query wording similarity is diagnostic only.
- Redundancy: repeated queries/fetches adding no new evidence. Deliberate verification and changed source content are recorded separately.
- Funnel: queries -> results -> unique sources fetched -> candidate jobs -> evidence-valid jobs -> reviewed useful jobs. Preserve rejection/failure counts at each stage.
- Coverage: assigned role/geography/source lanes actually investigated, with useful yield per lane.
- Verification coverage: shortlisted roles checked against direct employer or authoritative posting / shortlisted roles.
- Recovery: eligible failed attempts followed by a successful useful alternative / eligible failures; define scenarios before testing.
- Contribution: unique useful jobs contributed by each worker plus distinct evidence contributions. Uniqueness alone does not prove causality.
- Handoff loss: evidence-valid worker findings missing from final output without a recorded merge/rejection reason.
- Coordination overhead: coordination model/tool costs, messages and waiting time, compared with useful incremental output.

## Evaluation sequence

1. Implement and verify isolated workspace routing, central budget reservations and trace recording with fake tools. Test concurrency, failure and no production writes without paid calls.
2. Reuse frozen assessment examples for filtering/review evaluation. They measure interpretation, not discovery strategy.
3. Add a small searchable frozen corpus or query-aware simulated search tool to compare paths under stable evidence. Do not replay only one arm's queries and call that a fair search test.
4. Preflight and run bounded live paired A/B tests. Preserve raw search responses and fetched evidence privately.
5. Pool and canonicalize findings; label them without arm/worker identity. Use a fixed rubric. Any model judge is auxiliary and calibrated against human labels; count its cost.
6. Produce per-run scores, paired differences, mean/range and individual traces. With a small pilot, report uncertainty and avoid statistical significance claims. Record failed and budget-exhausted runs, never silently omit them.

## Deliverables and adoption rule

Deliver a comparison CSV/JSON, readable report, per-job evidence trails and per-run chronological traces. Report both fixed-budget outcome quality and fixed-workload speed. Set practical improvement thresholds before viewing results. Adopt multiple workers only if the observed improvement in yield or latency justifies total cost and operational complexity without unacceptable evidence/precision regressions. Otherwise retain the single worker and use traces to identify the next change.

## Candidate background

Private profile and supplied Markdown resume are snapshotted in private/comparison. Resume reports German B1; earlier background says very basic German. Preserve this discrepancy and do not assume professional fluency. Dated employment and earlier approximate experience totals must not be summed blindly. No resume content or personal contact details belong in public experiment reports.
