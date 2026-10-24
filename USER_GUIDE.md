# Operating your Job Seeker

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

The configured schedule is weekdays at 09:17 Europe/Berlin, with a weekend guard. It is subject to enabled settings, storage health and budget availability. Paid research stops at the production review gate; a completed status does not prove a new search ran or that a job was found. Public board reads may continue without paid research.

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
to start vacancy research. Both operations use the same cumulative spending gate
and serialized worker, so they cannot bypass each other's reservations.

Tune `[company_discovery]` in the configuration: `run_usd`, `max_searches`,
`max_pages`, `max_model_calls`, `focus`, `themes`, `lookback_months` and
`include_older`. The default company ceiling is $0.25 and never exceeds the
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
