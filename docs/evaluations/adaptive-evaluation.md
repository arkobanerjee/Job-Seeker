# Adaptive research acceptance — 24 October 2026

Eight fixed-content checks passed twice: job fit/conflicts/unknown eligibility,
index handling, concrete funding/product events, biographies and negated claims.
These are small synthetic checks, separate from fresh-market search evaluation.

| Fresh-search comparison | Fixed approach | Adaptive approach |
|---|---:|---:|
| Company leads passing the evidence gate (six searches/eight pages) | 0 | 3 |
| Vacancy candidates with body evidence (six searches/sixteen pages) | 1 | 6 |
| Larger vacancy run elapsed seconds | 146.84 | 198.61 |
| Larger vacancy run model calls | 11 | 17 |

The six vacancy candidates comprise three strong/possible fits and three
stretches. An initial nine were reduced by source checks excluding title-only
pages and an application-form duplicate. These deterministic guards were added
and tested after capture, then replayed on captured results; this is not a fresh
end-to-end rerun of their effect on navigation. All findings require manual
review. Company signals do not establish suitable vacancies or hiring intent.

An earlier eight-page vacancy pair yielded no shortlisted job in either
vacancy-specific arm. A failed earlier pilot is retained in private artifacts,
including context and token-limit failures; it is not used as a fair quality
comparison. Live arms ran sequentially with changing search results, and medium
reasoning plus replanning were changed together. No statistical superiority,
market recall or independent model-quality score is claimed. The design keeps
fixed checks, traces and live results distinct, consistent with [OpenAI evaluation
guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

## Fixes found through evaluation

- Bound multilingual page excerpts and observed-link lists by bytes; flag omitted
  source text for manual review and retain full private evidence.
- Keep company refinements away from vacancy queries and premature careers visits.
- Recognize explicitly stated headcount expansion without inferring suitable hiring.
- Assess the final fetched page before declaring resources exhausted.
- Record token-exhausted assessments and available usage; continue without findings
  for that page, retaining charges and avoiding blind retries.
- Exclude title-only job snippets and application forms as vacancy descriptions.

## Cost, rollout and recommendation

All test data stays in private/comparison/adaptive/. No experiment results were
imported into production. Additional reservations total $2.5912 under the unchanged
$2.80 cap; recorded cost estimate is $0.6485, with one older truncated call still
unreconciled. The separate experiment gate is $3.6472 / $5. Production budget is
unchanged.

The merged dashboard/control plane has been deployed and verified, including
both tabs, authentication, company aggregation, timeline code and Telegram
webhook. Production settings, catalog, registry and history remain unchanged.
Runner fixes require the acceptance PR to merge before GitHub Actions uses them.
Adaptive vacancy research remains opt-in. The manual company ceiling defaults to
$0.40 with 8,000-token adaptive output headroom, always under existing gates.

Recommendation: retain one worker and trial adaptive manual searches. Repeat
labelled comparisons before changing scheduling or claiming better precision.


## Deployment confirmation — 24 October 2026

The acceptance fixes are merged and CI passed. Cloudflare has been redeployed. Adaptive manual discovery is now enabled with medium reasoning and the tested bounded settings. Profile/resume, weekday monitoring and existing production records were preserved. No experiment results were imported and no production research was started during verification. The earlier rollout paragraph records the pre-activation state. The production reservation gate has $0.4848 remaining; it was not reset.
