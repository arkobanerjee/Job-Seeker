# Job Seeker

Personal job research in Python with LangChain/LangGraph, a configurable hosted model,
editable prompts, Markdown resume input, and a durable queue of opportunities and
rejected roles. Research is read-only; applications are always a human decision.

## Start locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
Copy-Item .env.example .env
New-Item -ItemType Directory -Force private
Copy-Item profile.example.md private/profile.md
```

Do not overwrite an existing .env or profile. Fill OPENAI_API_KEY and TAVILY_API_KEY
in .env. Then edit private/profile.md and optionally create private/resume.md.

```powershell
.\.venv\Scripts\python.exe -m job_seeker.cli check
.\.venv\Scripts\python.exe -m job_seeker.cli preview-prompt
.\.venv\Scripts\python.exe -m job_seeker.cli run
.\.venv\Scripts\python.exe -m job_seeker.cli dashboard
```

The dashboard opens at http://127.0.0.1:8765. The run command makes paid model/search
calls. Check and prompt preview do not. The rendered prompt is saved privately to
private/rendered-prompt.md.

## What to tune

| File | Purpose |
|---|---|
| config.toml | Provider, exact model ID, reasoning, token limits, prices, queries, budgets and prompt paths |
| prompts/master.md | Editable search/matching instructions, with profile and resume placeholders |
| private/profile.md | Your search preferences and confirmed background facts |
| private/resume.md | Optional resume in Markdown; loaded automatically when present |

Default model: OpenAI **gpt-5.6-luna**. Standard rates checked 2026-10-23:
$0.20/M input and $1.20/M output. To change models, explicitly set provider, model ID
and both correct prices. Incorrect prices invalidate spending estimates. Anthropic's
adapter is available but not live-tested; it uses normal generation and does not apply
the OpenAI reasoning_effort setting. No automatic fallback occurs.
[Official Luna model reference](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

Defaults: six basic searches, twelve page reads, sixteen model calls, 4,000 output
tokens/call, $2/run, and the existing $5 cumulative review gate. Increasing search
limits does not bypass monetary limits. The remaining prototype budget is not
automatically unlocked. Credentials stay in .env. Private files and runs are excluded
from Git. Configuration and prompt files must not contain credentials.

## How it works

1. Search configured AI and data queries with balanced candidate queues.
2. Fetch public pages under source policies; prioritize direct ATS listings and follow
   observed vacancy links from index pages.
3. Assess one page per small model call against the rendered background prompt.
4. Check source/title/quote evidence. Save verified-source findings separately from
   unverified suggestions. Keep technical matches with blockers as exclusions.
5. Save the catalog, decision history, per-run prompt/settings and checkpoints.

Each finding records company, role, URL, location, language, eligibility, evidence,
fit, concerns and rejection reasons. Marking **apply anyway** changes your decision
without erasing the assessment or sending an application. New observations preserve
your decisions/notes. General job indexes are discovery sources, not hiring companies.

```powershell
python -m job_seeker.cli resume --run-id <run-id>
python -m job_seeker.cli import-history
```

Resume uses the original run's saved settings and prompt. Completed steps are not
repeated. An interrupted in-flight request may be charged and repeated on explicit
resume; its earlier reservation remains. Evidence failures are retained privately in
rejected_findings as unverified, not as confirmed job leads.

Source text is untrusted data. Tools cannot log in, contact people, submit applications,
execute code, or read arbitrary URLs. Missing language/authorization facts stay unknown.
Evidence checks do not prove current vacancy availability or legal eligibility.

## Cloud and Telegram

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Cloudflare Worker/R2 dashboard, private
GitHub Actions worker, secrets setup and acceptance steps. No recurring job is enabled
until deployment and budget review. Cloud state has a 20 MB limit and one serialized
writer. Each cloud run reserves its whole ceiling before starting, so a killed runner
cannot reset the budget.

Enable notifications.telegram only after setting TELEGRAM_BOT_TOKEN and your
TELEGRAM_CHAT_ID. Telegram currently sends owner completion summaries. Questions/replies
are not implemented; the cloud dashboard provides remote search and profile editing.

## Verification

```powershell
python -m unittest discover -s tests -v
node --test cloud/worker.test.js
```

Tests cover evidence, prompt ingestion, budgets, restart behavior, human decisions,
archive boundaries, authentication and concurrent reservations. The old demo, plan,
research and review commands remain for pilot compatibility. Use **run** for the new
configurable runner; legacy research retains its earlier pilot defaults.

Luna and Tavily passed a live smoke test. Search quality still depends on queries and
source access. Cloud deployment needs its own acceptance run before it is production-ready.

## Discovery evidence

Findings include discovery_trails with search queries, result ranks, run IDs,
observation times and paths reconstructed from saved search results and observed
links. Both dashboards display these under How was this found? Missing historical
evidence stays unavailable. These paths are evidence, not model reasoning logs.

## Clarifications (pending deployment acceptance)

The assessor can request consequential candidate input. The runner persists a
waiting_user checkpoint and question, then exits. With Telegram enabled, answer
by replying directly to the bot question. Question IDs stay internal; the old
/answer command remains supported for older messages. Cloud replies require a webhook secret and
the configured private owner chat; answers are immutable and resume the saved run.
Resume reuses that run's budget envelope and per-call ledger. Answers are task input,
not permission to contact employers. Duplicate replies can queue redundant serialized
runners, but completed runs return their saved result.

Deployment requires TELEGRAM_WEBHOOK_SECRET and TELEGRAM_CHAT_ID Worker secrets,
a Telegram setWebhook registration pointing to /telegram with that secret_token,
and notifications.telegram=true in cloud settings. These are not enabled by this PR.
Dashboard question controls and automatic delivery retry are still pending.

## Company and source registry

Both dashboards expose Companies and source history. The private registry retains
company/source associations, ATS host detection, retrieval timestamps and content
hashes across runs. Source observations are idempotent per run; inaccessible pages
remain unavailable rather than closed. Changes describe retrieved text, not job counts
or hiring predictions. Identity currently uses normalized company names, so aliases
need later reconciliation. Official source ownership remains unverified.

The registry is populated from saved checkpoints and future research. It does not yet
automatically schedule source checks, collect structured ATS feeds, or discover official
career landing pages. Those are the next monitoring milestone. The SQLite registry
travels in the private cloud snapshot and its dashboard export is authenticated.

## Repeat monitoring

Use Check saved sources in the cloud dashboard (or python -m job_seeker.cloud monitor
in the configured GitHub workflow). Monitoring revisits the least recently observed
sources within page and spending caps and issues no discovery search queries.
Assessments are reused only when source input, links, policy, profile, prompt, model
settings, schema and search track match. Changed input gets assessed again. Failed
fetches remain unavailable, not closed. Cached findings retain human decisions.

Set monitoring.enabled=true in config.toml for local monitoring. Daily scheduling is available but requires monitoring.schedule_enabled=true
in private cloud settings. First checks may require fresh assessments because older runs did not
cache them. Cloud still reserves the configured whole-run ceiling, even if a check
ultimately needs no model calls; a zero-cost repeat is not guaranteed.

## Structured ATS retrieval

Recognized Greenhouse and Lever hosted boards/postings use their documented public
GET endpoints, including Lever EU. Collection retains the original listing URL and
API evidence URL. Board indexes expose at most 30 same-tenant posting links without
an LLM call; individual postings follow the normal evidence/fit assessment. Boards
are bounded samples, not full inventories: absent jobs do not establish closure.
Public network checks, endpoint robots policy, response size and page limits apply.
Unsupported sources continue through ordinary public-page retrieval.

References: https://docs.greenhouse.io/job-board.html and
https://github.com/lever/postings-api . No application-submission endpoints are used.

## Daily monitoring and notifications

The shared serialized workflow runs at 09:17 Europe/Berlin, Monday–Friday. GitHub may delay scheduled
runs. Set monitoring.schedule_enabled=true in private cloud config to opt in; the
default is false. monitoring.daily_run_usd defaults to $0.25 and cannot raise the
normal per-run ceiling. The existing cumulative $5 review gate remains unchanged.
Checks skip without spending if disabled, waiting for a user, or short of budget.
Daily claims prevent duplicate scheduled runs; an interrupted claim is not retried
automatically the same day. Last completion/skip reason is visible in the dashboard.

Scheduled completion notifications include new or materially changed opportunities
only. Unchanged findings are quiet; required questions and run errors still notify.
Material fields include role, fit, language, eligibility, concerns and evidence.
This is conservative field comparison rather than a semantic change classifier.
Manual runs retain their completion summaries. Notification delivery retry remains
a separate outstanding reliability task. No automatic budget reset or increase occurs.

## Operations dashboard

Questions waiting for you can be answered in the authenticated dashboard as well as
Telegram. Answers are tied to the stored revision, immutable once accepted, and queue
the saved run. If dispatch fails, retry the identical answer. Run history shows status,
progress, errors, limitations and reported usage estimates; prompts and page text are
excluded. Continue saved run is available only for recoverable cloud runs with an
existing budget envelope. History appears after the next checkpoint sync.

Multi-worker performance experiments are deferred until single-worker completion.

## Public company signals

Enable signals.enabled with configured signal queries to use company, hiring,
technology, product and organizational-change routes. Up to signals.max_queries
replace slots within limits.max_searches, preserving at least one vacancy query.
Signal families rotate through a persistent cursor; monitoring issues no searches.
Signals require matching retrieved source IDs, verbatim quotes and company text.
Event dates stay unknown unless the ISO date appears explicitly in the source.
These checks do not prove source ownership or the model interpretation.

Signals are retained separately in the company registry and reports, not promoted
to vacancies. The assessor may follow supplied careers/vacancy links within the same
page and spending caps. No hiring probabilities are inferred. Signals do not yet
provide hiring-momentum trends, independent corroboration or competitor expansion.
