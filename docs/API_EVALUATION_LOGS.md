# Search and API evaluation logs

New vacancy research, company discovery and monitoring automatically write a
private `runs/<run_id>/evaluation.json`. No opt-in or extra LLM evaluator is
required. Public board observations retain retrieval receipts. Historical runs
are not assigned invented query explanations or API usage.

## Locations

- Hosted dashboard: **Run history → Search and API performance → Load saved
  evaluation log**. Download full JSON or a search comparison CSV. Downloads go
  to the browser's configured download folder.
- Local research: `runs/<run_id>/evaluation.json` under the workspace root.
  The local dashboard has a **Search and API evaluation logs** section with links.
- Hosted research: files in the temporary GitHub runner are checkpointed in
  private R2 `state/latest.zip` as `runs/<run_id>/evaluation.json`.
  A separately retrievable export lives in bucket `job-seeker-private` at
  **`evaluation/<run_id>.json`**.
- Authenticated API: `GET /api/evaluation/<run_id>`. Use dashboard bearer
  authentication; do not put credentials in a URL.
- Private run-evidence archive ZIPs also include evaluation.json. Individual
  R2 evaluation exports are not removed by evidence archival. They have no
  automatic deletion policy and consume storage beyond the active snapshot.

Hosted runs do not automatically create permanent copies on your PC. Download
the log when you want a local copy.

## Search results and query revisions

Each search attempt has an ID, exact query, origin, round, results and outcome.
Result entries preserve URL/title/snippet, rank and score, including entries
rejected by the source guard. This records returned search snippets, not the
full body of every linked page. Fetched bodies remain in private source evidence.

Adaptive query notes include a parent search ID when revising a prior query,
short decision explanation, expected improvement, target country and strategy.
Parent IDs must actually exist; invalid references are flagged. Missing notes
stay unknown, with the batch explanation available as a fallback. New independent
queries have no parent. Configured company-theme seeds receive deterministic
coverage explanations. Proposed and admitted plans are recorded separately from
executed requests.

Per-query metrics include returned/admitted/new/overlapping URLs, fetched and
available pages, processed pages, unread result URLs, vacancy candidates,
excluded roles, rejected proposals and qualified companies. Additional records
are attributed by first successful search order through observed source links.
Cache hits do not earn discovery credit. Tracking parameters are normalized;
different posting URLs are not guaranteed to represent different jobs. A processed
ATS index may not require a model call. Unread results remain unevaluated.

Each search also links downstream page-assessment/review call IDs by observed
source paths, with known model cost and unknown-cost counts. Shared sources can
link the same call to several searches: these per-query costs must not be summed
as if they were exclusive. Use unique call IDs or the purpose totals for spending.
Planner cost is retained under planning rather than arbitrarily divided among
the queries in its batch.

## API coverage

Model purposes are planning, clarification preflight, page assessment,
independent review and corroboration. Receipts retain model/effort, input hash
and bytes, configured prices/output limit, structured output, available usage,
reservation ID, cost estimate, duration and outcome. Review changes retain
before/after fields. Finding catalog IDs can be joined to separate human decisions.
Applying is feedback, not a ground-truth quality label.

Logical source-fetch receipts cover public pages/ATS access, cached reuse and
rejections. Public retrieval and robots checks have HTTP status, timing and byte
counts. Redirects may involve several requests inside one logical receipt.

Telegram delivery and Cloudflare state/control requests made inside the research
session receive operational receipts. Notification retries outside that session
retain existing outbox records. Initial state loading, Worker-side GitHub dispatch,
R2 internal suboperations and dependency downloads are outside this run-scoped
instrumentation. It is not a complete provider billing audit. No invented per-call
fee is assigned to HTTP, Telegram or storage. Log upload excludes itself to avoid
recursive logging.

Comparison workers retain per-task model/search/retrieval receipts alongside their
existing traces; aggregate scoring remains in experiment reports. Check the
`attribution_available` flag before using query metrics from a partial adapter.

Raw prompts, resume/background inputs, candidate answers, request headers and
credentials are omitted. Structured outputs can contain source quotations and
questions, so logs remain private.

## Persistence and limits

Start receipts are written before external execution, completed receipts afterward.
Atomic replacement has bounded retries for temporary Windows file locks. A start
without completion has an uncertain outcome; unknown paid usage stays unknown.
Resume preserves completed log receipts newer than the research checkpoint.
Accounting allowances and provider retry policy are unchanged.

Cloud checkpoints upload changed exports through authenticated endpoints with a
2 MB per-run export ceiling. Existing research-storage diagnostics still apply.
Backups and cold evidence archives include the local file. Cloud uploads retain
prior API IDs across a research restore. Attribution metrics describe saved
research snapshots and may differ after rollback. One serialized cloud writer
remains required.

## Measuring improvement

Telemetry measures observed contribution, overlap, latency and estimated cost.
It does not prove a rewritten query was causally better than an unexecuted
alternative. Candidate counts are not independently labelled useful jobs; a
reviewer changing a decision is not automatically a correction.

Compare strategies within the same geography, role family and comparable input
configuration. Use repeated equal-resource baseline/adaptive trials and review
a blinded sample. No automatic paid A/B runs or model judging are introduced.

JSON is the primary record. CSV exports search funnels and escapes spreadsheet
formula prefixes. Logging adds local I/O and cloud synchronization work, but no
additional model or Tavily requests. Reservations and cost estimates stay distinct.
