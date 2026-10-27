# Dashboard redesign task list

Prepared: 27 October 2026. Status: implemented locally; publication awaits owner approval.

## Delivery status

The first redesign is implemented locally. It includes the new dark-theme layout, separated action groups, button press and loading states, meaningful refresh feedback, preserved job/company/question/settings drafts, collapsible job and company cards, local filters, grouped company/source history, compact history and maintenance panels, and responsive layouts.

Activity is checked against GitHub execution status, with distinct queue, active, waiting, pause/cancel request, stopped, failure and unavailable states. The worker now records safe failure receipts when an initial progress upload fails. Request receipts prevent duplicate dispatch after a repeated submission. Workflow titles identify the requested operation while its first checkpoint is still pending.

Verification: 167 Python tests, 50 JavaScript tests, five simulated recovery drills, and browser checks at desktop and 390-pixel mobile widths passed. Visual previews use synthetic opportunities; no paid research or external messages were started.

Publication is pending. Automatic approval review rejected uploading source, tests, documentation and workflows to `arkobanerjee/Job-Seeker` because the user had not explicitly authorized that payload and destination. No repository changes or website deployment were performed.

Remaining release work after approval: publish the reviewed source, pass hosted CI, deploy the complete Worker module set, verify the authenticated live dashboard and activity endpoint, and confirm the formerly missing evaluation-upload route. Optional later refinements include richer preferences tabs and comparing only the changed fields in refresh summaries. Activity descriptions represent recorded actions; long in-flight requests can have an older last-activity timestamp.

## Review basis

Reviewed both supplied screenshots and the complete dashboard implementation in `cloud/page.js`, including login, actions, opportunity views, questions, history, settings, registry, storage, backups, archives and evaluation downloads. Checked the related Worker routes, run controls and runner checkpoint handling. This is a screenshot and source review, not a live browser walkthrough of every expanded panel.

The current interface gives almost everything the same visual weight. Research actions, administration and filters share a toolbar; operational information appears as loose paragraphs; opportunity cards expose long research text before the user can scan or decide. Most actions give feedback only through one shared status paragraph. There is no automatic status polling or reliable indication that a saved running checkpoint still has a live worker.

## Proposed page arrangement

1. **Header:** Job Seeker, connection state, Refresh and a quieter Sign out control.
2. **Activity:** a compact run-status panel with current operation, elapsed time, latest recorded action, last update, counters and relevant controls.
3. **Research actions:** Find job openings and Discover companies as the primary actions. Check saved sources and Check job boards as secondary actions in a labelled monitoring group.
4. **Needs your attention:** pending questions, actionable failures and uncertain notifications. Hide this area when empty.
5. **Your opportunities:** clear Job openings / Companies tabs; each view has its own bordered, collapsible container, counts and local filters.
6. **Supporting sections:** Run history, Company/source history, Preferences, and Maintenance. Routine healthy states stay compact; detail expands on demand.

Keep the dark theme, improve spacing and typography, and make the first screen answer: What is running? Does anything need me? Where are my opportunities?

## P0 — Make activity status trustworthy

- [ ] Investigate and resolve the evaluation-log upload 404 seen in today's discovery run. The route exists in local source; verify the deployed Worker and workflow versions before choosing a fix.
- [ ] Handle failures during initialization, checkpoint upload and finalization so a crash cannot permanently leave the last public summary marked Running.
- [ ] Associate each dispatched request with its execution and eventual research run. Record queued time, start time, last activity, finish time and execution outcome. Cover monitoring and maintenance operations as well as discovery.
- [ ] Reconcile saved research status with worker execution status. When updates are stale and execution cannot be verified, show **Status unavailable — last update …**. A timeout alone must not be presented as confirmed failure.
- [ ] Define distinct states: Inactive, Queued, Running, Waiting for your answer, Pause requested, Paused, Cancel requested, Cancelled, Completed, Stopped at a limit, Failed and Status unavailable.
- [ ] Preserve a safe, specific failure summary: what failed, when, whether saved progress exists and what recovery is supported. Keep raw diagnostics behind Details; never display credentials.
- [ ] Keep execution failures, research limits and notification delivery failures separate. A failed notification must not imply the research failed.
- [ ] Prevent duplicate dispatch from rapid clicks or request retries, while respecting the shared serialized worker queue. Show queued work separately from active work.

Acceptance: the October 27 failure displays Failed with an upload-related reason once reconciled; it cannot remain Running. Queueing is never mistaken for execution. A disconnected status check never falsely reports Inactive.

## P1 — Reorganize the layout and action groups

- [ ] Establish consistent typography, spacing, panel borders, corner radii, readable text widths and primary/secondary/destructive control styles.
- [ ] Separate account controls, research actions, monitoring actions and maintenance. Put backup, storage checks, archives and notification recovery inside their relevant supporting sections.
- [ ] Move job filters and search into the Job openings container. Label filters visibly instead of relying on placeholders or unexplained default values.
- [ ] Use a clear selected style for tabs and filters. Distinguish a persistent selection from a temporary button press.
- [ ] Replace the loose stack of disclosure headings with spaced, bordered sections and short summary information.
- [ ] Replace long spending and notification paragraphs with compact summaries. Expand the explanation of reserved spending versus observed estimates when requested.
- [ ] Display pending-question and failure counts where they can be noticed without opening every section.

Acceptance: a user can distinguish starting research, filtering results and maintaining the system without reading the entire page. Secondary tools do not crowd the main actions.

## P1 — Make every interaction give useful feedback

- [ ] Add a subtle pressed/depressed appearance to action buttons, restoring it on release. Support keyboard focus and reduced-motion preferences.
- [ ] Give asynchronous actions a visible pending state, such as Queuing… or Saving…, and disable repeat submission while that request is unresolved.
- [ ] Show confirmation beside the relevant action or item. Use a compact shared notice only for page-level events; routine messages must not erase persistent failures.
- [ ] Make Refresh show Refreshing…, then **Up to date — no changes** or a real change summary, such as **2 new jobs; activity updated**. Count meaningful data changes rather than changing timestamps.
- [ ] Show Last checked separately from Last activity. A successful refresh does not mean the background task made progress.
- [ ] Show partial refresh failures per section and retain prior data with a stale label. Avoid a generic instruction to check the budget for every request error.
- [ ] Preserve unsaved notes, company drafts, settings edits, filters, active tab, expanded cards and reading position during refresh and status polling. Current refresh replaces the settings editor contents.
- [ ] Use persistent **Unsaved changes** and local Saved feedback for editable forms.

Acceptance: a button press is immediately visible; the request outcome is clear; refreshing with no new data says so; polling never clears an answer, draft or settings edit.

## P1 — Build the activity mini-dashboard

- [ ] Show current operation in plain language: Finding job openings, Discovering companies, Checking saved sources, or the actual maintenance task.
- [ ] Show status, elapsed duration, start time and last confirmed activity time. Freeze the timer at completion and distinguish paused/waiting time from active execution where available.
- [ ] Translate recorded actions into a short current-step description: Preparing search, Searching for …, Reading …, Assessing a listing, Saving results, or Waiting for your answer.
- [ ] Add a small expandable recent-activity timeline and counters for searches, pages and findings. Clearly label older or incomplete receipts.
- [ ] Poll activity automatically while authenticated and work is queued/running; slow down when idle, pause unnecessary polling in a hidden tab and stop on sign out. Refresh activity independently of editable views.
- [ ] Show Pause, Cancel and Continue only when supported. Explain request-pending states and that an in-flight action may finish first.
- [ ] Include a durable failure message and relevant Details/recovery control. Never automatically start paid research as a side effect of refreshing status.

Use observable actions and saved explanations, similar to an assistant's activity feed. Do not invent internal thinking, exact progress percentages or an ETA when the workload is unknown.

Acceptance: without opening Run history, the user can tell whether work is inactive, queued, progressing, waiting, stopped or failed, and when that information was last confirmed.

## P2 — Make opportunities easy to scan

- [ ] Put **Job openings and application decisions** inside a bordered, padded, collapsible section. Keep its heading, counts and chevron visible when collapsed; open it by default on the jobs tab.
- [ ] Make each job card independently expandable. Its collapsed summary shows company, role, application decision, location/remote arrangement, fit assessment and listing verification status.
- [ ] In expanded cards, group content as Summary, Requirements and concerns, Evidence, and Your decision. Keep Open listing easy to find; place detailed discovery trails and independent-review receipts behind labelled disclosures.
- [ ] Preserve important blockers and unconfirmed availability in the compact summary. Shortening a card must not make an uncertain listing look verified.
- [ ] Keep notes and decision controls together with local save feedback and an explicit indication when a saved decision moves a card out of the current filter.
- [ ] Apply the same card structure to Companies: company, qualification, evidence count and decision first; supporting evidence, earlier notes and editable introduction on expansion.
- [ ] Add company-specific search and decision/qualification filters; clarify the difference between companies worth investigating and suitable open jobs.
- [ ] Show filtered counts alongside totals and provide a clear Reset filters action and useful empty states.
- [ ] Fix the visibly broken company/title separator (`â€”`) and audit user-visible text for similar encoding defects. Do not blindly rewrite saved source evidence.

Acceptance: several opportunities can be compared without scrolling through full research essays. Both the entire opportunity section and individual cards can collapse independently.

## P2 — Tidy every supporting section

- [ ] **Questions:** show the question and why it matters, keep answers local, disable duplicate submission and show whether the answer was saved and continuation accepted.
- [ ] **Run history:** compact rows with operation, status, local date, duration and result counts; expand for failure details, timeline, limitations and evaluations. Keep internal run IDs secondary.
- [ ] **Search/API evaluations:** lead with an understandable result/usage summary; put raw receipts and model outputs in advanced details; show loading, unavailable and download states.
- [ ] **Company/source history:** separate company records, source observations and board trends; avoid one undifferentiated sequence of large articles. Make observation date and source uncertainty easy to identify.
- [ ] **Preferences:** provide named tabs for Search settings, Research instructions, Profile and Resume, with descriptions, unsaved-state protection and clear save feedback. Keep the raw configuration editor available under Advanced.
- [ ] **Storage:** human-readable sizes, capacity and last check; show stale diagnostics as needing a fresh check rather than as an asserted storage failure.
- [ ] **Backups/archives:** compact dated rows, readable sizes, downloads and local feedback. Keep the existing explicit restore acknowledgement next to the selected backup.
- [ ] **Monitoring/notifications:** translate codes such as `not_checked` into plain language. Distinguish not enabled, not yet checked and failed; place retry next to the affected delivery state.
- [ ] **Login/session:** label the token input, show Connecting… and specific connection feedback, and clear private data and polling on sign out.

## P3 — Verify the finished experience

- [ ] Check desktop, narrow window and mobile layouts: no clipped search fields, overflowing URLs, textareas or raw log blocks.
- [ ] Verify keyboard navigation, labelled inputs, meaningful focus, accessible disclosures/tabs, contrast and status announcements. Never rely on color alone.
- [ ] Exercise queued, running, waiting, paused, completed, failed, stale and offline activity states, including a worker crash before the first search.
- [ ] Verify duplicate-click protection, refresh with/without changes, partial endpoint failure, draft preservation and correct dispatch of every existing action.
- [ ] Verify decisions, evidence trails, company grouping, restore acknowledgements, private downloads and per-run allowances survive the redesign.
- [ ] Render representative populated and empty states, including long titles, unknown fields and failure messages; visually inspect before release.
- [ ] Verify the deployed Worker and background execution versions together so the website and worker agree on their API contract.

## Suggested implementation order

1. Trustworthy execution status and failure recovery (P0).
2. Layout, action feedback and activity panel (P1).
3. Collapsible opportunities and supporting sections (P2).
4. Interaction/accessibility checks and deployment verification (P3).

The visual shell can be developed alongside P0, but a live Running indicator should only ship with the status safeguards. Implementation is available locally; publication and live acceptance remain pending owner approval. No paid research runs were started.
