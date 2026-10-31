# Session handoff (2026-10-31)

Start here: docs/REQUIREMENTS.md (what the applicant wants + mistakes so far), then HANDOFF_PROMPT.md.

State of data (branch deterministic-pipeline):
- data/export/batch1.xlsx: first attempt (369 Chinese-surname candidates, 226 with email). Rows from
  official directories (Duke, WashU, UVA, BU, USF) are usable; rows from paper search (data/roster/ps-*.jsonl,
  UCSF / Mount Sinai / UMich / UPenn) are hints only: no titles, misses new faculty.
- data/discovery/v2/*.jsonl: per-school department scouting with coverage status (UCSF, Mount Sinai, UMich,
  most of UPenn blocked from the cloud sandbox).
- docs/cshl_bioai.md: CSHL BioAI PhD facts and young PIs (contact PIs before applying; rolling from Dec 15).
- Earlier CS work (data/roster/csr-*, CSRankings) is kept but out of scope (applicant does not want CS).
Tools: outreach/{fetch,roster,enrich,papers,validate,score,shortlist,audit,papersource}.py; playbooks in agents/.
Secrets (not in git): secrets/openalex_key (OpenAlex daily budget is small; Europe PMC needs no key).
