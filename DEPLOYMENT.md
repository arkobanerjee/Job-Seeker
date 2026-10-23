# Deployment and acceptance

The Python worker runs locally or in GitHub Actions. Cloudflare serves an authenticated
dashboard/control API and stores private state in R2. The initial version uses R2
instead of a separate D1 database: one owner, one serialized worker, small snapshots.
The dashboard token is kept only in browser memory, so sign in again after a refresh.

## Local operation

1. Fill `.env` using `.env.example`. Do not put credentials in configuration or prompts.
2. Copy `profile.example.md` to `private/profile.md` if no profile exists. Optionally
   create `private/resume.md`. Markdown is loaded directly; PDF conversion is not included.
3. Edit `config.toml` and `prompts/master.md`.
4. Run `python -m job_seeker.cli check`, then `python -m job_seeker.cli run`.
5. Run `python -m job_seeker.cli dashboard`; open http://127.0.0.1:8765.

## Cloud credentials

Store these locally in `.env`:

R2 management can use a separate `R2_API_TOKEN` (the API token value from the R2
Admin Read & Write token screen). The deployment helper uses that token for bucket
management, and retains `CLOUDFLARE_API_TOKEN` for Workers. S3 Access Key ID and
Secret Access Key are separate credentials, not bearer tokens for the REST API.

- `CLOUDFLARE_ACCOUNT_ID`: account ID (not zone ID).
- `CLOUDFLARE_API_TOKEN`: scoped to this account, Workers Scripts Edit, Workers R2
  Storage Edit, Account Settings Read, and Workers Subdomain Edit when available.
  Register a workers.dev subdomain in the dashboard and activate R2 if not already done.
- `GITHUB_DEPLOY_TOKEN`: fine-grained token scoped only to Job-Seeker. Actions write
  enables dispatch; Environments write configures the production environment and its
  secrets. Secrets write is needed only if using repository secrets manually. It is
  preferable to replace the dispatch credential later with an Actions-only token.
- `TELEGRAM_CHAT_ID`: your private conversation ID with the bot. Start the bot first.
  Notifications stay off until this is configured and enabled in config.toml.

`scripts/deploy.py` generates `JOB_SEEKER_APP_TOKEN` locally and saves the deployed
`JOB_SEEKER_URL` to `.env`. Do not expose the R2 bucket via r2.dev or a public domain.
Never upload `.env`, private/, or runs/ to GitHub, including as Actions artifacts.

## Provisioning order

1. Merge the reviewed application PR into main. CI must pass first.
2. Install deployment-only dependency `python -m pip install pynacl`.
3. `python scripts/deploy.py worker` creates the private bucket, deploys the Worker,
   and enables its workers.dev address. It fails if account permissions are missing.
4. `python scripts/deploy.py github-secrets` creates the production environment,
   restricts it to main, and encrypts API credentials with GitHub's environment public key.
5. With no local run active, `python -m job_seeker.cloud bootstrap` uploads private
   state and migrates the accumulated local budget. Initialization cannot reset an
   existing cloud budget. If initialization succeeds but upload fails, use the
   authenticated Cloud.sync and Cloud.settings methods after checking existing state;
   never delete budget.json to retry.
6. Sign in to the dashboard using JOB_SEEKER_APP_TOKEN from your own .env. Run one
   bounded search and verify private data access, model results, rejected-role decisions,
   checkpoint uploads and notifications before enabling a schedule.

The research workflow accepts workflow_dispatch from the dashboard and a daily
09:17 Europe/Berlin schedule. Scheduled research requires monitoring.schedule_enabled
in private cloud settings and sufficient remaining budget. It uses one concurrency group and never cancels an
active run. Resumption accepts a run ID in the workflow's optional input. Never run
independent cloud writers against the same bucket. Local runs after migration use a
separate ledger and are not combined with cloud spending; use cloud as the sole live
runner after cutover.

## Budget and recovery

The existing $5 review gate and $2 run ceiling remain. Raising them requires a separate
budget decision; the remaining $15 is not automatically unlocked by deployment.
Cloud reserves the full run ceiling atomically before starting paid work. Reservations
are not refunded after a crash, and a fresh runner cannot reset the global allowance.
Local per-call estimates remain visible in each run's result. Cloud reservations are
deliberately more conservative than those estimates.

State is saved after completed queries and page assessments. Explicit resume uses
the original prompt/config and does not redo completed steps. A provider call interrupted
before its result was saved can be repeated on resume; its earlier reservation remains.
This is application checkpointing around LangGraph nodes, not a general agent sandbox.

If a token expires, refresh that credential and rerun deployment/secrets setup without
resetting budgets. Storage preflight warns at 75% of the byte or file ceiling and blocks research at
90%, before reserving paid work. Inspect Storage health on the dashboard and request
a fresh check if it is stale. Backups retain five private snapshots but do not shrink
the active state. Weekday maintenance moves eligible terminal-run evidence into private cold archives.
It keeps the newest 20 runs and at least 30 days of evidence in active state, and
protects resumable tasks, unresolved questions and outstanding delivery receipts.
Every cold archive must pass checksum upload and readback before its active evidence
is removed. Persistent databases are not pruned. Stop and plan database migration
if those databases alone approach the capacity limit. Keep financial,
question, delivery, catalog and registry records. A large in-flight run can still reach
the limit; the preflight cannot predict its final size. Cloud job failures remain visible in
GitHub; a killed process cannot reliably send a final Telegram message.

## Current boundaries

- Text-only public research; no login/browser/code tools, outreach or auto-applications.
- Telegram delivers owner-only questions and summaries. Reply to a question normally;
  standalone text is accepted only when exactly one question is pending. The dashboard
  also supports answers and continuation, and pause/cancel take effect at tool boundaries.
- OpenAI Luna passed a live smoke test. Other configured models/providers require their
  correct prices and a small acceptance test; there is no automatic fallback.
- External source facts and model fit judgements still require review. Search coverage
  is bounded, and index pages are not employer leads.
- Cloud HTTP endpoints, private R2, GitHub Actions and deployment credentials require
  an end-to-end cloud acceptance run before calling the deployment production-ready.

References: [Cloudflare upload metadata](https://developers.cloudflare.com/workers/configuration/multipart-upload-metadata/),
[R2 conditional writes](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/),
[GitHub secret encryption](https://docs.github.com/en/rest/actions/secrets),
[GPT 5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).


## Storage checks and recovery rehearsal

The dashboard's **Check storage health** queues a serialized, no-research workflow.
It validates the allowlisted ZIP, reports compressed/expanded bytes and file counts,
and runs SQLite quick_check on current databases. An absent budget ledger blocks
research. Other databases may be absent before their first use. Integrity checks do
not prove business-level consistency or recover a damaged database.

Reports refer to one snapshot version. The dashboard labels them stale when state
changes; refresh the check before relying on it. A failed workflow may leave an old
report, so inspect its timestamp and GitHub result. No model or search calls are made.

Use **Create private backup** and verify its appearance in Private backups. Download
and validate a copy for an isolated rehearsal before a real restore. A restore is
queued through the serialized workflow, creates a pre-restore backup and preserves
current financial records, delivery receipts, questions and preferences. It rejects
concurrent state replacement. Restoring research is still an intentional rollback;
it does not recreate new research that was absent from the chosen snapshot. The
bucket is private; no public GitHub artifacts hold these files. Same-account copies
do not protect against account loss. Keep an independently secured copy if needed.

## Frozen quality evaluation

The repository includes 14 **synthetic, manually labelled** examples in
`tests/fixtures/quality_cases.json`. They cover positive AI/data roles, mandatory vs
preferred German, seniority, unstated authorization, explicit location/citizenship
restrictions, closed listings, company announcements, aggregate indexes, prompt
injection and overlapping experience. These are regression examples, not a measured
sample of the labour market or an immigration assessment.

Prepare inputs with labels removed:

```
python -m job_seeker.evaluation prepare --output private/evaluation-inputs.json
```

Collect independent Assessment objects in a JSON mapping from case ID to output.
Use the configured master prompt and profile when producing those assessments; keep
reference labels out of the model context. Store results privately. This preparation
and scoring tool never invokes a model or spends credits. Live model generation must
use the existing bounded worker accounting; do not start an unmetered benchmark.

Score saved outputs:

```
python -m job_seeker.evaluation score --predictions private/evaluation-predictions.json --output private/evaluation-report.json
```

The scorer applies production title/quote/closed-page checks and index filtering,
then reports per-case errors, shortlist precision/recall, false shortlists and misses.
It also checks designated unknown fields and rejection explanations. Missing outputs
fail and count as missed relevant roles; a zero-shortlist precision is reported as
unavailable rather than perfect. Any failing example returns a nonzero exit status.
Scorer unit tests use explicitly authored outputs and do not establish model accuracy.
This evaluates extraction decisions, not independent reviewer quality, search recall,
source freshness over time or live availability. Add independently labelled real
examples privately before a release decision, and hold some out when tuning prompts.


## Operating policy after acceptance

- Keep a single serialized cloud writer. Weekday schedule remains 09:17 Europe/Berlin;
  no automatic weekend research. The scheduled workflow runs notification recovery,
  maintenance, then its bounded research check.
- Keep the $5 cumulative review gate, $2 maximum run reservation and $0.25 scheduled
  cap. There is no monthly reset and no automatic unlock of the original $20 allowance.
  Compare provider billing with local observed estimates before approving more credit.
  Missing usage, killed calls and ambiguous delivery keep their reservations. Do not
  refund the difference between reservations and estimates automatically.
- A dedicated acceptance run reserves at most $0.40 in the same cloud gate before
  any model calls, with an isolated private ledger and no Tavily searches. Its ledger
  is separate from the live research snapshot; the global envelope remains charged.
  `python -m job_seeker.acceptance` is explicit paid work, never part of CI or the
  weekday schedule. Keep its outputs under private/acceptance.
- Active evidence retention: keep the newest 20 runs and at least 30 days. Only
  completed/cancelled tasks can move to cold storage. Partial, failed, waiting and
  paused tasks stay active. Preserve all catalog decisions, observations, company
  memory, budgets, questions and delivery records. Download cold evidence through
  the private dashboard. It does not automatically resume archived terminal tasks.
- Cold evidence archives are immutable and have no automatic deletion. The five-copy
  rolling backup policy is separate. Review cold-storage usage and account billing
  monthly; same-account R2 storage does not protect against account loss. A partial
  archive upload or checksum conflict stops maintenance; retain hot evidence and
  inspect the private objects rather than overriding the conflict.
- Byte/file preflight still warns at 75% and stops research at 90%. Cold archival does
  not solve unbounded growth of the catalog/registry databases. That threshold is the
  stop-and-migrate point, not permission to delete financial or decision history.
- Recovery drills run with `python -m job_seeker.drills` locally and in CI. They use
  actual runner/outbox code with injected tools, provider interruption and delivery
  outcomes in an isolated temporary workspace. They do not send Telegram messages or
  prove real provider delivery under every network failure. Interrupted assessments
  may need retry; completed searches/pages must not repeat.

## Acceptance evidence (2026-10-23)

Merged PR15 diagnostics passed in the serialized live workflow. A fresh private
backup was verified identical to current research before dispatching a live restore.
That restore completed successfully; budget, questions, outbox, catalog, config,
master prompt and profile bytes were preserved. This validates same-snapshot recovery,
not a historical rollback after real data loss. An earlier isolated restore rehearsal
also passed. Isolated pause/continue, terminal cancel, saved-progress restart,
definite notification failure/recovery, and uncertain-send suppression passed.

The configured OpenAI model completed 14 frozen synthetic assessments and four
independent reviewer probes with no provider errors. The **strict scorer passed
8/14**. Shortlist precision/recall were 1.0 within this small set, with zero false
shortlists and zero missed suitable cases. These figures are not real-market recall.
Four failures were exact-string mismatches: the model said forms such as “Unknown;
no authorization or sponsorship information stated” where the rubric requires the
literal “unknown”. The remaining two concerned closed-listing title/category handling
and a company announcement returned as a signal rather than a watchlist finding.
The original report is retained unchanged; labels were not revised after the run.

The reviewer rejected both proposed matches containing explicit German/seniority
blockers and returned manual_review for the two proposals with unknown authorization.
This is four probes, not a calibrated reviewer accuracy result. Before calling the
product fully accepted, define the representation of unknowns, closed/rejected jobs
and signal-only responses, then freeze a separate labelled real-source/held-out set.
Do not tune to these examples and report a rescore as new held-out performance.
No two-worker benchmark is authorized by this acceptance run.
