
## 2026-10-31 batch 1 rebuild
- Grid scouted for 10 schools; 6 rostered (~50 units). Roster verifiers: USF 5 FAIL / BU 4 / Duke 4 / MS 2 /
  UCSF 1 -> fixed (name parser: nicknames, initials, accents, degrees, badges; pagination; fallback pages).
- 240 young Chinese-surname candidates -> enrich -> Haiku tags + Sonnet second opinion.
- Auditor: 10/45 sampled rows had a content error (junk homepages, duplicate person, non-advising titles,
  same-name papers); 0/106 title or email failures. Fixes in batch1.py clean/dedupe/split_papers/evidence.
- Result: 57 People, 15 Need email, 42 Check, 125 Dropped.
