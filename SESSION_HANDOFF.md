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

Session 2, later decisions:
- Applicant: skip CS for now (too competitive). CS done for 11 schools only (csr-*), the rest paused.
- Non-CS order: neuroscience > comp-bio / biomedical informatics > biostat > statistics > ECE (ml_only).
  Queue: data/discovery/to_enrich_pri.txt. Directory scrape failures (403 / JS / wrong URL): ~40 units, skipped.
- Run slowly: one department at a time, --workers 2, one judge agent at a time (applicant shares the token budget).
- Shortlist: python -m outreach.shortlist -> data/export/shortlist.xlsx (first version sent: 160 CS candidates).

## Paused (applicant out of credits). Resume, in this order, slowly:
1. Paper refill (OpenAlex rate-limited earlier), neuro/comp-bio/biostat first:
   for f in $(grep -l "rate limited" data/dossiers/*.jsonl | grep -v csr-); do python -m outreach.enrich $f --refill-papers; done
2. Remaining department enrich (skips finished ones):
   while read f; do [ -f data/dossiers/$(basename $f) ] || python -m outreach.enrich $f --workers 2; done < data/discovery/to_enrich_pri.txt
3. Judge (ONE haiku agent at a time, ~7 files each): python -m outreach.judge prep data/dossiers/<dept>.jsonl,
   then agents/25_judge.md; then python -m outreach.judge assemble <dept>.
   Already judged non-CS: brown neuro, cmu neuroscience, mit csb, brown/bu/columbia biostat (re-assemble after refill).
4. python -m outreach.shortlist --no-cs -> data/export/shortlist_noncs.xlsx, send to applicant.
5. Email stage: applicant will provide a writing skill.
