# Session handoff (2026-10-30, session 2)

Applicant decision: only young faculty (assistant / incoming / recent associate); Chinese & other Asian surnames
first (loose match, Lee/Long count). Goal = enough well-matched professors to email, not completeness.

Built (branch `deterministic-pipeline`):
- outreach/roster.py (YAML selectors per directory; config/directories/cmu-stat.yaml, cmu-lti.yaml)
- outreach/csrankings.py: 831 young CS faculty with >=2 ML/CV/NLP/bio papers since 2021, 54 schools
  (353 Chinese surname). Young = first CSRankings paper >= 2012 (calibrated on CMU titles).
- outreach/enrich.py: dossier per person, no LLM. Email only if on an official page (+CV PDF, contact page),
  JS homepages rendered with Playwright, CSRankings rows joined to department profile pages by name.
- outreach/papers.py: OpenAlex (key in secrets/openalex_key, gitignored) by institution id; drops >30-author papers;
  same-name candidates confirmed by page titles, else closest to page text (flagged). S2 fallback.
- outreach/judge.py + agents/25_judge.md: haiku judges relevance/keywords/fit from ~200-token summaries;
  assemble keeps only keywords present in source text.
- Pilot CMU Stat: 38/38 records pass validate.py; vs. pilot agent records: 19 same emails, 4 extra found,
  0 wrong-person emails.

Open:
1. (done) OpenAlex key installed; csr-* enrich rerun with it.
2. CS emails ~45% from homepages; add department directory YAMLs (CS/MLD/ECE) per school for the join.
3. Stats/biostat/comp-bio directories for other schools (agent writes YAML, young titles only).
4. Judge outputs for csr-* dossiers, then assemble + merge, then email stage (separate skill).
