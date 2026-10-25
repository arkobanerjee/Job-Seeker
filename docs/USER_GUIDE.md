# Operating your Job Seeker

For query revision history, complete search-result snapshots, API cost receipts
and JSON/CSV downloads, see [Search and API evaluation logs](API_EVALUATION_LOGS.md).

Open https://job-seeker.arko-bbanerjee.workers.dev and sign in with your dashboard password. Keep the password and API credentials private.

## Normal routine

1. Review shortlisted jobs and open the original posting before deciding to apply. Fit and availability assessments can be wrong or stale.
2. Review rejected/manual-review records too. Relevant jobs remain there with barriers such as language, seniority or location, so you can choose to apply anyway.
3. Check pending questions in the dashboard or Telegram. Reply directly to the bot's question. A standalone reply works when exactly one question is pending; otherwise reply to the specific message.
4. Mark your decisions in the dashboard. The app researches opportunities; it does not submit applications or contact employers.

## Choosing an operation

- Discovery searches the web through Tavily and reads selected pages. Search queries and limits come from configuration. It can incur search and model charges.
- Monitoring revisits saved sources. Zero searches can be normal: a run may read known URLs and reuse unchanged assessments.
- Observe public job boards reads supported public board counts without paid model/search calls. It does not assess job fit. Trends require comparable observations on different dates.
- Continue saved run resumes an eligible interrupted task within its existing limits. Pause takes effect at tool boundaries; a call already running may finish. Cancel is terminal.
- Notification recovery handles saved delivery attempts. Uncertain deliveries are not automatically retried because that could duplicate messages.

## Updating your background

Open Settings, master prompt, profile and resume. Select private/resume.md to edit the Markdown CV, private/profile.md for preferences and constraints, or prompts/master.md for search/matching instructions. Save each edited file. Changes apply to subsequent runs; old runs preserve their original context and limitations.

The resume now supplied does not retroactively change older cards saying no resume was supplied. German B1 in the CV differs from the earlier basic-German description; the background records this uncertainty.

## Changing model and search behavior

In config.toml, model controls provider/name/reasoning/output size and pricing assumptions. Set accurate prices when switching models. Search queries control discovery; limits bound searches, pages, model calls and run allowance. Keep changes small and inspect the next run. API credentials belong in local .env or encrypted deployment secrets, never dashboard text files or GitHub source.

Local configuration and live dashboard configuration are separate copies. Editing local .env does not automatically update deployed secrets. Avoid running local production research against the same cloud state while the GitHub worker is active.

## Schedule and spending

The configured schedule is weekdays at 09:17 Europe/Berlin, with a weekend guard. It is subject to enabled settings, storage health and budget availability. Paid research stops at the saved per-run allowance; a completed status does not prove a new search ran or that a job was found. Public board reads may continue without paid research.

Production and comparison allowances are independent. Comparison results stay under private/comparison and never populate the app. Current operating choice is setup A, one sequential researcher. The experiment's GPT-6 Luna selection does not change the production model.

## Understanding run history

Searches count external search calls. Pages count retrieval attempts, including unavailable pages. Model calls count assessment/review calls. Findings can include excluded/reference records; they are not necessarily suitable open jobs.

The improved history card adds a plain-language activity explanation and expandable exact search queries, saved result URLs and fetched-page outcomes. Limitations are grouped separately. These are saved observations, not a complete ordered decision trace. Some older runs lack detailed evidence; the UI must say so rather than invent it. Richer history appears after the updated backend exports run summaries.

## Troubleshooting

- No Telegram question: questions are sent only when clarification is necessary. Check pending questions and delivery status; silence alone is not a failure.
- Zero new jobs: inspect queries, unavailable pages, index pages, limits and excluded records. A completed run can legitimately find none.
- Budget blocked: review the spending ledger before authorizing any increase. Conservative reservations remain charged after uncertain calls.
- Storage warning: inspect health and archival status before another large run. Restore preserves current budgets, receipts and separate cloud settings; it is not a spending reset.
- An old card mentions missing CV: this reflects that run's historical context, not the current background.

## Local comparison tools

See experiments/README.md. Default execution is offline; --live explicitly makes paid calls. The completed three-setup suite is exploratory: independent workers were faster, but quality was not established. Keep setup A for current operation and review evidence before changing architecture.

## Company opportunities

This separate queue shows company signals, positive comparable board changes and competitor leads. These are reasons to investigate, not confirmed vacancies or proof of expansion. Open the evidence, read uncertainty, and save new/watch/investigate/draft outreach/dismissed plus notes. Prepare editable introduction creates a local template; Save company decision stores it privately. No messages are sent. A lack of cards can mean no recorded signals, insufficient trend history or disabled competitor research.

## Tabs and research coverage

Use Job openings and Company opportunities tabs to switch queues. Refresh preserves the selected tab for the current session. Job filters apply only to the job queue. Company cards reflect collected evidence, not all companies that expanded over a date range. Current Tavily search requests have no explicit date filter and do not exhaustively cover six months. Signal research shares the bounded query/page allowance with vacancy searches. Multiple signals for the same company and source collapse into one card; momentum needs comparable observations on different dates, and competitor cards require discovered evidence. A historical company-news backfill is a separate research workload requiring its own scope and spending allowance.


## Adaptive research (opt-in, awaiting acceptance)

The `[adaptive]` section in the search configuration enables bounded planning,
search, page inspection and replanning for new discovery runs. Use
`enabled=true` to opt in; leave it disabled for normal production until the
isolated acceptance comparison is complete. Existing saved runs keep their
configuration snapshot.

`planning_effort` and `assessment_effort` default to `medium` for OpenAI.
`max_high_escalations` caps planner-requested high-reasoning assessment batches.
Tune `max_rounds`, `queries_per_round`, `pages_per_round`, `max_minutes` and
`max_stalled_rounds` alongside the existing total search/page/model/spending
limits. Reaching a search limit still permits inspecting already found pages.
A research round with no new finding or company signal counts as stalled.

Questions arrive through the existing Telegram reply interface. Waiting pauses
the time allowance, while all spending and counters remain attached to the saved
run. Stops preserve unfinished work and an explicit stop reason. The JSON run
artifacts include `research_trace`; dashboard trace presentation is a later step.
The dedicated company-discovery operation is also a later step.


### Tuning adaptive vacancy searches

`[vacancy] role_families` defines AI/data role synonyms; `regions` defines preferred
search areas. These are planning hints, not automatic exclusion rules. Your
profile and resume still supply candidate facts. `navigation_links` limits
observed career/ATS navigation links automatically queued per page (default two).
Searches and navigation share the existing run allowance.

The next planning round receives failed-page status and earlier rejection
reasons. It can change role titles or sources and inspect an observed individual
posting behind a careers index. This can improve discovery, but a query attempt
or a careers link does not establish a current suitable vacancy.


## Discover companies

After deployment, click **Discover companies** to queue a manual company research
run. Review results in **Company opportunities**. **Find job openings** continues
to start vacancy research. Both operations use the same serialized worker and retain their own saved per-run allowances. Cumulative spending is recorded but does not block later runs.

Tune `[company_discovery]` in the configuration: `run_usd`, `max_searches`,
`max_pages`, `max_model_calls`, `focus`, `themes`, `lookback_months` and
`include_older`. The default company ceiling is $0.50 and never exceeds the
configured general run-dollar ceiling. Smaller allowances can stop before all
themes are searched; query/page/model limits are ceilings, not promised usage.

Themes cover funding, expansion, product, deployment and team announcements.
The default six-month search-date hint is anchored to the saved run start.
Set `include_older=true` for older-history research. Search dates must still be
checked against actual source evidence; undated events remain unknown.

Local command: `python -m job_seeker.cli company --config config.toml`.
GitHub Actions: select workflow mode `company`. The cloud worker invokes
`python -m job_seeker.cloud company`. Saved company runs resume normally with
their existing limits. No automatic company schedule is added.

Company activity does not establish a suitable opening. Stronger qualification
labels and combined evidence cards are the next implementation steps.


### Company evidence labels and review

Company opportunities shows counts for qualified opportunities, investigation
leads and rejected evidence. Expand **Investigation, dismissed and rejected evidence** to
inspect weak or historical signals, competitor relationships, board activity and
failed quote/source claims. Each held record includes its review reason. Your
notes and decisions remain available; changing a decision does not change its
evidence qualification.

A qualified signal passed quote, company-name, event-wording and shared-profile-
term checks. It still requires judgment: these checks do not independently prove
the event, publisher ownership, candidate fit or a suitable vacancy. Labels
separate funding, expansion, hiring/team growth, products and deployments.
Missing event dates display Unknown. Historical records remain in investigation
until assessed under the new rules; no paid reprocessing happens automatically.


### Combined company cards and preserved notes

Each company has one card. Expand its **evidence groups / source URLs** section
to inspect each excerpt, qualification status, event date, source link and run
reference. Matching excerpts are grouped as copies; several source URLs do not
prove independent corroboration. Different excerpts remain separate for review.

Company names merge after case/spacing normalization or through your configured
aliases. Different companies sharing an ATS or publishing host are kept separate.
New evidence does not change the company's card ID or reset your decision.

Earlier notes from individual-source cards or configured aliases appear under
**Preserved earlier notes and decisions**. The newest earlier decision is used
until you save a company-level decision. Saving a new combined note retains the
older notes in history. Dismissed companies stay in the collapsed review section
when more evidence arrives; you can change their status to watch or investigate.


## Read the research timeline

Open **Run history**, then expand **Research timeline** on a run. It shows the
recorded sequence: planning explanations, admitted queries, search results, pages
attempted, HTTP failures, navigation, model calls, saved-assessment reuse, signal
qualification, questions and round outcomes. Use the stop reason and unread-page
count to understand what remains unfinished. Review the plan's coverage gaps;
completion means bounded work ended, not that the internet was exhausted.

The timeline is a tool-action record with short decision explanations. It does
not expose internal model reasoning or full prompts, resume text or your answer
contents. A start without a matching completion receipt has an uncertain outcome.
Old runs may have no chronological records or only partial saved records; the UI
labels this instead of inventing a history.

The dashboard limits trace size and states how many earlier events were omitted.
Full saved receipts remain in private checkpoint/result evidence (and archived
run evidence after archival). **What was searched and read** still supplies the
separate saved query/source summary for older runs.


## Acceptance configuration and remaining rollout

The live dashboard now includes the company operation, evidence groups and
research timeline. Runner fixes discovered during acceptance require their PR
to be merged before the next GitHub Actions run uses them. Adaptive vacancy
research remains opt-in: the small live comparison has not established improved
useful-job yield. Company discovery is a separate explicit manual operation.

After the acceptance fixes are merged, `[adaptive] max_output_tokens` controls
assessment/planning output headroom (default 8,000). `[company_discovery] run_usd`
defaults to $0.50. This is a maximum conservative reservation, not an expected
invoice amount. The smaller operation/general per-run allowance applies. There is no cumulative gate. Resuming keeps the original run allowance; a new run gets a new allowance. No additional scheduled company run is added.

Long pages and link lists are bounded for model input. If relevant source text
was omitted, a vacancy proposal remains for manual review. Output-token
exhaustion is recorded as a page-level assessment failure; the worker continues
with other evidence and does not invent a finding for that page.

Evaluation artifacts remain in private/comparison/adaptive/ and never populate
your real queues. A new manual production run collects its own evidence.


The final larger vacancy trial found six candidates with description evidence
versus one from configured queries; three were stronger/possible matches and
three were stretches. Results vary and require review. Title-only JavaScript
pages and application forms are retained as unverified evidence rather than
promoted as assessed vacancies. Browser rendering is not added by this change.
See evaluations/adaptive-evaluation.md for evaluation limits and rollout status.


Spending history is informational. Vacancy and company runs currently allow $0.50 each; weekday monitoring allows $0.25. Reaching a spending limit saves a partial result without a provider-failure flag. Repeated runs have no overall cumulative cap.


## Proactive questions and remembered preferences

Enable `[clarification] enabled=true` in private cloud configuration to check
candidate preferences before a new vacancy or company search. Existing cloud
configs without this section keep the previous behavior until enabled. The check
asks one focused question when an unresolved preference would materially change
scope or recommendations, rather than requiring research to become impossible.
It can proceed without asking when the profile and saved answers are sufficient.
A preflight check is an ordinary model call within the same run spending/call limits.

The planner and page assessor can ask about recurring ambiguities during research.
By default, at most two new questions are allowed per run across all three paths.
Questions pause the same saved run and appear on Telegram and in the dashboard.
Reply normally to the bot; the existing owner-only reply path queues resumption.
No model calls or web searches are repeated merely because a pending answer is
checked again. Resuming keeps the original spending allowance. Waiting for an
answer is excluded from the execution-time allowance.

Answers consumed by the worker are saved privately inside questions.sqlite3 and
reused in later runs. This database already travels with private state and is
preserved by restoration. Answers are task data, not tool permissions. Raw answers
and question text are not added to public action traces. Candidate preference data
is bounded before model input; omitted old answers remain unknown.

Tune `preflight`, `max_questions_per_run`, and `reuse_answers`. Turning reuse off
ignores older runs' answers while still using answers given in the current run.
Optional `[clarification.preferences]` keys are `geography`, `seniority`,
`internships`, `sponsorship`, `work_arrangement`, and `compensation`; explicit
current preferences take precedence over older answers. Use these to pre-answer
known preferences without waiting for a question. Do not include credentials.
Routine saved-source monitoring does not initiate new preference questions.

The agent asks what you are willing to consider or what support you need. It must
not ask you to establish an employer's sponsorship policy, language requirement
or hiring status. Those remain source-research questions or unknown facts. It
does not send employer messages. Question generation is a model decision; this
feature does not force a quota of questions or create a conversation every run.


## Applied jobs and saving decisions

The job list opens in **To review**, hiding Applied and Dismissed records.
Choose a status on a job card and click **Save decision**. A successful Applied
save immediately moves the job out of To review; the application-status badge,
counts and feedback update. Choose **Applied** in the application-status filter
to see it again, or **All application statuses** to see the whole catalog.
The role-category filter is separate; selecting Applied resets it to All.

Saving a decision records your action and notes; it does not submit an application.
Notes persist after refresh and across later research observations. Errors appear
beside the button, and a failed save does not change the stored status. Unsaved
notes on other job cards survive saving one job. Existing applied decisions are
honored immediately; jobs do not need to be marked again after this update.

## Startup directories and funding publications

Company discovery now deliberately searches configured startup sources alongside
its funding/expansion/product/deployment/team themes. The defaults are
`ycombinator.com/companies`, `eu-startups.com`, and `tech.eu`.
Set `[company_discovery] startup_source_queries` (default 2, maximum 3, 0 disables)
and `startup_sources` to tune this. The first preferred source is always included;
remaining slots rotate through other sources based on the saved UTC run date.
Restarts retain the same seed plan. These queries share the company's existing
search, page, time, round and $0.50 per-run limits; they are not extra unlimited work.
With small allowances, not every theme/source will be inspected. Exact executed
queries and visited pages appear in the research timeline.

A YC directory entry is a company-discovery pointer, not evidence of a recent
funding round or a suitable vacancy. Directory searches omit the recent-date hint
because directory indexing dates are not funding dates. Funding-publication and
other event searches retain the configured lookback hint, which still requires
checking the actual event date. The agent should follow original company/investor
announcements. Unsupported membership-only funding claims stay in investigation;
unknown dates stay unknown. Public pages only: no new accounts, login automation,
paid data subscriptions or LinkedIn dependency are introduced.

Sources: [YC directory](https://www.ycombinator.com/companies) and
[YC's separate job board](https://www.ycombinator.com/jobs).
