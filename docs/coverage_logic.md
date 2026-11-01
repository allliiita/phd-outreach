# Coverage logic (how batch 1 searched; follow the same order when adding schools or filling gaps)

Goal: young, PhD-advising, Chinese-surname faculty who DO AI / ML (Bio-AI welcome, not required), so the
applicant can become an AI research scientist. Departments are search handles; people are judged one by one.

## Handles, in this order, at every school
| # | Handle | Examples | How |
|---|---|---|---|
| G1 | AI core schools/departments | CS, ECE/EE, Statistics & Data Science, data-science schools (BU CDS, USF Bellini), other engineering depts (ME, systems, materials, industrial) | full official faculty list, every rank page |
| G2 | AI institutes, centers, initiatives, new AI departments | Duke Discovery AI, Duke AI Health, Mount Sinai Windreich AI dept, BU Hariri / CISE, UCSF Bakar / Computational Precision Health, joint Berkeley–UCSF programs | member / faculty lists |
| G3 | NeuroAI homes | neuroscience / neurobiology depts and programs, CSHL | full list; keep only computational / ML people |
| G4 | Molecular / biomedical computation | BME, chemistry, pharmacology, biostatistics & bioinformatics (in medical school), comp-bio PhD programs, imaging-AI centers | full list; keep only computational / ML people |
| + | New hires | "new faculty" news 2024–2026 of engineering / CS / data-science / medical schools | incoming assistant professors are often only there |
| + | School-wide keyword search | only where the directory supports it (UCSF Profiles), restricted to G1–G4-type homes | keywords: machine learning, deep learning, AI, ... |

## Never
Clinical departments (medicine, pediatrics, surgery, ophthalmology, psychiatry services, ...), schools of public
health, UCSF Epidemiology & Biostatistics, business schools. Sites behind a bot check are recorded as blocked,
never worked around. Schools the applicant postponed: WashU, UVA, UMich, UPenn.

## Unit census (completeness of UNITS, not people) — agents/07_unit_census.md
Before rostering, and again before a list is final, an independent agent enumerates every unit from the
school's official lists — the graduate school's list of all PhD programs (every unit that can admit a PhD
student is on it), schools & departments pages, the centers & institutes directory, and 2023–2026 news of
new AI / data / computing units — and marks each covered / out of scope (why) / added. Output:
data/grid/<slug>.units.jsonl -> "Unit census" sheet. A unit marked "added" goes into the grid as todo.

## Every unit ends with a status (Coverage sheet)
done (N rows, verifier verdict) | partial (why) | blocked (URL) | none at this school | skipped (applicant).
Gaps are found by reading the Coverage sheet top-down: a school without a G1/G2 row is the first place to look.
