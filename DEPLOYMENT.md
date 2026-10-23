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
resetting budgets. If the cloud state reaches 20 MB, stop and archive old run evidence
before continuing. Keep budgets and the catalog. Cloud job failures remain visible in
GitHub; a killed process cannot reliably send a final Telegram message.

## Current boundaries

- Text-only public research; no login/browser/code tools, outreach or auto-applications.
- Telegram sends owner-only completion summaries; conversational questions/replies and
  webhook commands are not implemented. The dashboard supplies remote control/editing.
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
