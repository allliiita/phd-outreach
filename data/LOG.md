
## 2026-10-31 batch 1 rebuild
- Grid scouted for 10 schools; 6 rostered (~50 units). Roster verifiers: USF 5 FAIL / BU 4 / Duke 4 / MS 2 /
  UCSF 1 -> fixed (name parser: nicknames, initials, accents, degrees, badges; pagination; fallback pages).
- 240 young Chinese-surname candidates -> enrich -> Haiku tags + Sonnet second opinion.
- Auditor: 10/45 sampled rows had a content error (junk homepages, duplicate person, non-advising titles,
  same-name papers); 0/106 title or email failures. Fixes in batch1.py clean/dedupe/split_papers/evidence.
- Result: 57 People, 15 Need email, 42 Check, 125 Dropped.

## 2026-11-02 list v1 frozen (data/export/list_v1_2026-11-02.xlsx, git tag list-v1)
Batch 1: BU, Duke, USF, UCSF, CSHL, Mount Sinai. Batch 2: JHU, UCF, Cornell (+Cornell Tech, Weill AI units), Rockefeller.
Sheets: {'People': 61, 'People (batch 2)': 46, 'Need email': 24, "Apply directly, don't email": 7, 'Strong fit, not young': 1, 'Says not recruiting': 2, 'Check (title or fit)': 58, 'Dropped (C)': 205, 'CSHL (any heritage)': 23, 'Coverage': 163, 'Unit census': 342}
Rules: young PhD-advising titles; Chinese surnames; fit A/B (C dropped); priority NeuroAI = trustworthy-ML > AI depts > CS-type ML >
molecular; >=3 top-ML papers 2023-26 (dblp) moves up one tier; within tier: recruiting > top-ML papers > fit.
Checks: roster verifiers per school; 713/719 dossier quotes found on saved pages; email validation (surname-only list-page emails rejected).
