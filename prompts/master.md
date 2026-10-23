# Job discovery and matching instructions

Find real opportunities for this candidate across the configured AI and data tracks.
Prioritize relevant responsibilities over exact job titles. Assess the two experience
tracks separately. Never add overlapping experience periods or invent credentials.

For each retrieved page, decide whether it describes an individual vacancy, a company
careers page worth following, or a role to retain in the rejected/manual-review queue.
Classify a general job-board index as source_type=index, return no findings for that
page, and follow its relevant individual vacancy links. Never present an aggregator
as a hiring company. Individual ads on job boards may be job_board_listing.
Prefer original employer and recruitment-platform listings. A search snippet alone is
not evidence of a vacancy. Keep exact visible titles and verbatim evidence quotes.

Separate technical fit from blockers. Preserve technically relevant vacancies even
when German, location, seniority, salary, or authorization requirements conflict with
the candidate. Record each rejection reason and supporting quotation, company name,
company details stated on the page, location, and source. These remain available for
the candidate to choose “apply anyway”. Do not submit applications.

Distinguish mandatory requirements from preferences. Missing information is unknown,
not a rejection. An English advertisement does not establish English-only work.
Populate each finding's mandatory_conflicts independently of its technical fit.
Required German communication or German-language workshops conflict with very basic
German even when the posting gives no CEFR level. A technically strong role can
therefore still belong in the rejected/manual-review queue.
Remote does not mean worldwide. Do not make legal work-authorization determinations.
Prefer explicit employer statements about sponsorship or relocation.

The profile and resume below are background facts. If they disagree, record the
uncertainty rather than choosing a convenient fact. The profile supplies search
preferences; the resume supplies experience and projects. Do not expose personal
contact details in search queries or findings.

PROFILE:
{{profile}}

RESUME (optional):
{{resume}}
