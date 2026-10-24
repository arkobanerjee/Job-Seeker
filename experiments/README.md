# Isolated worker comparison

## Expanded three-configuration suite

`python -m experiments.comparison --suite` runs an offline smoke suite. Add `--live` explicitly for paid execution: three briefs (Germany AI, Germany data, international), two repeats, all three arms, 18 runs total. The full worst-case allowance must fit the persistent experiment $5 gate before launch. Each run gets two searches, up to three pages per subtask and at most two independent reviews. Arm order is counterbalanced across the six trials. Results and an aggregate report are saved under private/comparison/suites/; each trial retains separate traces and snapshots.

C uses two parallel researchers with an atomic shared URL ownership map. A worker encountering an already-claimed URL skips it and moves to another source. This deterministic coordinator adds no model calls; it tests coverage sharing, not an LLM supervisor. Failed claims remain owned for the run, which can reduce cross-worker recovery or cross-track reassessment. All arms prioritize observed vacancy links over navigation and use the same model/prompt and limits. C is an experimental extension; production remains single-worker.

This package is a separate local experimental runner. Production workflows do not import it. It reuses controlled HTTP/search, structured assessment, evidence validation and reviewer components. It never calls the production runner or cloud client.

Prepare private inputs once with `python scripts/prepare_comparison.py`. Re-running preparation refreshes candidate input snapshots; it does not reset the persistent experiment ledger. Then run `python -m experiments.comparison` for a free, network-free synthetic A/B pair. Outputs are private under `private/comparison/results/`.

The initial pilot assigns the same two fixed queries to one sequential researcher (A) or two concurrent researchers (B). Each subtask gets one search and up to two fetched/assessed pages. Both arms use identical evidence checks, merge rules and a maximum of two independent reviews. This measures fixed task execution and context separation; it does not implement an autonomous planning/coordination agent (C).

An explicit `python -m experiments.comparison --live` launches one paid pair. The launcher passes only the selected model API key and Tavily key to a fresh child process. No deployment, dashboard, Cloudflare or Telegram credentials are passed. Credentials are read from the local .env without printing or copying them. No paid run is performed by tests, imports or default commands.

Live runs reserve each paid call centrally in the separate experiment SQLite ledger. The persistent $5 cumulative gate and $0.30 per-arm cap are enforced with database transactions across threads. Preflight requires space for a complete $0.60 pair and checks the worst-case call envelope. Failed/uncertain calls keep reservations. Do not manually delete the budget database to bypass the cap. The serialized experiment lock prevents concurrent batches.

The private experiment.json controls model/provider selection and contains the $5 isolation policy. Task queries and per-task limits are deliberately fixed for this first pilot. Model price assumptions are validated by the application settings. There is no automatic provider fallback.

The comparison now uses GPT-6 Luna at verified standard USD 0.10 input / 0.50 output per million tokens (2026-10-23). Production model selection is independent. Optional per_arm_usd may reduce the default USD 0.30 envelope; it cannot increase it. Pair preflight reserves headroom for twice that envelope. Complete fetched pages are retained as artifacts; assessment context projects relevant fields and bounds links instead of passing unbounded board metadata.

Every batch freezes prompt, configuration, tasks and input hashes, and writes reports, CSV/JSON, a pooled human-label worksheet and chronological traces. Traces link query results, sources, assessments, review, deduplication, failures and reservations. Private artifacts may contain resume information; keep the entire workspace out of GitHub and public reports.

Default simulation uses deterministic stand-ins and a finite searchable corpus. Its timing and output quality are not real agent performance results. It verifies isolation and accounting mechanics. The live pilot uses the same conservative finding validation as the app, but is intentionally smaller than the production pipeline: signals, competitor discovery, board monitoring, outbox and durable clarification/resumption are excluded. Questions are saved locally; no user messages are sent. This is a local capability boundary, not an OS sandbox for untrusted code.

Inspect report.md and fill review-labels.json before making quality claims. More briefs and repeated paired runs are necessary for useful architecture conclusions. See comparison-plan.md in the workspace for the broader protocol.


## Production adaptive-runner acceptance

`python -m experiments.adaptive_acceptance --live` evaluates the actual runner
in isolated per-arm roots, including fixed-content cases and fresh fixed/adaptive
searches. It requires explicit paid execution and launches a child containing
only model/search credentials. No GitHub, Cloudflare or Telegram credentials are
passed, notifications/schedules are disabled, and all charges use the existing
private/comparison/budget.sqlite3 $5 gate. A persistent adaptive-allowance.json
bounds this acceptance series to its original additional $2.80 ceiling; failed
calls and repeated evaluations do not reset it. It refuses a full batch when the
remaining allowance is insufficient. Source captures, manifests, reference
labels, predictions and all traces remain private.

`--resume-batch <id>` explicitly verifies saved interrupted checkpoints with a
maximum additional $0.08 reservation per arm; it preserves old reservations and
before-resume metrics. `--vacancy-pair` runs the final larger equal-budget vacancy
check (at most $0.90 across both arms), still under that same persistent allowance.
These commands do not deploy code or change production settings. Fixed-content
cases and live runs measure different things; small sequential live samples do
not establish market recall or isolate the effect of reasoning from replanning.
