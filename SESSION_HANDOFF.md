# Session handoff (2026-10-31, batch 1 rebuild)

Start: docs/REQUIREMENTS.md, then config/targets.yaml (bottom block = current scope, agreed with the applicant
2026-10-31: 6 schools BU, Duke, USF, UCSF, CSHL, Mount Sinai; WashU/UVA/UMich/UPenn postponed; CS IN;
PhD-advising young titles only; Chinese surnames; per-person fit A/B/C; priority NeuroAI > AI depts/initiatives
> CS-type ML > molecular ML).

Pipeline (all in outreach/batch1.py; playbooks in agents/):
1. grid scouting: agents/05b_grid_scout.md -> data/discovery/v3/<school>.jsonl
2. rosters: agents/10b_roster_batch1.md (one worker per school) -> data/grid/<school>.jsonl + data/roster/
   verify: agents/15_roster_verifier.md (fresh agent) -> data/grid/<school>.verdicts.jsonl; fix; code check
3. python -m outreach.batch1 enrich | cards | (taggers: agents/26_fit_tagger.md, Haiku) | recards (Sonnet
   second opinion) | validate | export -> data/export/batch1.xlsx
4. auditor: agents/60_auditor.md (Sonnet). Findings and fixes listed at the end of that file.
Access: config/browser_hosts.txt (hosts read in real Chromium; bot checks are never worked around).
UMich, Penn Medicine/SEAS, UCSF dept sites, Moffitt, WashU MIR are challenge-blocked from the cloud.

State (superseded): 57 People (A/B with verified email), 15 Need email (UCSF mostly), 42 Check, 125 Dropped (C).
Open: associates' promotion year unverified; UCSF emails; BU Psych & Brain Sciences, Mount Sinai Psychiatry /
Neurology, Duke DIBS not rostered; target 200-300 needs more schools (WashU first) or wider surnames.

## Update 2026-11-02: list v1 frozen
data/export/list_v1_2026-11-02.xlsx (git tag list-v1): People 61 (batch 1) + People (batch 2) 46, Need email 24,
Apply directly (don't email) 7. Batch 2 = JHU, UCF, Cornell, Rockefeller (JHU blocked pages saved by the applicant into
data/snapshots/manual/). Unit census sheet covers every school. Side task running: docs/ai_lab_phd_sources.md (where top-AI-lab
researchers did their PhDs). Next: decide email pilot (10 profs) vs more schools (Rutgers, Stony Brook, NJIT; Columbia later).
