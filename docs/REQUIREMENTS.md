# What the applicant wants (source of truth — read this first)

## Goal
Find professors Lindsey Ma (M.S. Statistics, Columbia 2026; CV in config/applicant.yaml and her CV PDF) can
email about a Fall 2027 PhD, and who might plausibly take her. Not a census of everyone, but **no
target department silently skipped**: every (school × department) in scope must end with an explicit status.
Batch 1 = about 200–300 professors with verified emails.

## Who counts
- **Schools (batch 1)**: Boston University, Icahn School of Medicine at Mount Sinai, University of Pennsylvania,
  University of Virginia, Duke University, University of South Florida, Washington University in St. Louis,
  University of Michigan, UCSF, and Cold Spring Harbor Laboratory (BioAI PhD; see docs/cshl_bioai.md).
  Excluded by the applicant: Harvard, MIT, Yale, Brown, CMU, all Texas schools, SUNY Buffalo, remote Midwest
  schools; other research institutes postponed. (config/targets.yaml holds this list.)
- **Departments (types T2–T8)**: Biomedical Informatics / Biomedical Data Science / AI in Medicine;
  Computational Biology / Bioinformatics / Systems Biology / Genomics (computational faculty); Statistics &
  Data Science (NOT biostatistics in schools of public health); Biomedical Engineering (ML / imaging /
  computational faculty); Data Science institutes with their own faculty; Computational neuroscience; CS /
  ECE faculty doing AI for biology / health only. Plain CS / AI groups are not wanted.
- **People**: young faculty = Assistant Professor, Incoming Assistant Professor, or Associate Professor who
  started that rank recently (≈ 2020+). Chinese surnames only in batch 1 (loose: Lee, Long etc. count).
- **Research fit**: broad AI or Bio-AI (ML for biological / biomedical / neural data, statistical learning,
  representation learning, interpretability). Calcium imaging is past work, not a constraint.
- **A professor listed on the official department page is a valid target even with no papers found.**
  Papers are for personalising emails, never a reason to drop someone.

## Mistakes made so far (do not repeat)
1. Started from data sources (CSRankings, paper search) instead of from the target list; requirements changed
   and patches piled up. → Work target-first: the grid of school × department is the plan.
2. Discovered people from papers (Europe PMC last authors, ">=2 papers in 3 years"): misses new assistant
   professors and ML/stat people who publish at conferences, and gives no titles. → Official faculty pages
   are the only discovery source. Papers only enrich.
3. The cloud sandbox's IP is blocked (403 / SSL) by UCSF, Mount Sinai, UMich, UPenn med/engineering, cshl.edu.
   → Run on the applicant's own computer, or read blocked pages with a real browser (Claude in Chrome /
   built-in browser) and save them to data/snapshots/manual/.
4. Auto-scraped directories mixed in students, staff, emeritus, navigation text, other departments.
   → Check each roster against the page by eye (count + 3 random rows) before trusting it.
5. Ranking by a keyword score produced odd orders. → Fit is decided per person by a reader at email time.

## Deliverable
`data/export/batch1.xlsx` with: school, department, name, title (verbatim from official page), young? (from
title / start year), email (verbatim from an official page), homepage, 1-line research summary, 1–2 recent
paper titles if found, fit note — plus a **coverage sheet**: one row per school × department type with
status `done (N people) | none at this school | blocked (why) | not found (what was checked)`.
