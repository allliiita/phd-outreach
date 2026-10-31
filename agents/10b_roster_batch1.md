# Roster worker, batch 1 (one school) — read after 10_roster_worker.md; this file wins where they differ

Repo /home/user/phd-outreach. Read docs/REQUIREMENTS.md and config/targets.yaml (the comment block at the
bottom is the current scope). Your school's scouting is data/discovery/v3/<slug>.jsonl.

## Which units (departments are search handles; people are judged later, by code + a tagger)
G1 AI core (preferred home): Computer Science, ECE / EE, Statistics (& Data Science), data-science schools or
   institutes that appoint faculty, other engineering departments (mechanical, systems, industrial, materials)
   — ALL their faculty are rostered; relevance is decided per person later.
G2 AI-for-bio/medicine units and initiatives with their own or joint faculty lists (e.g. Duke AI Health,
   Duke Discovery AI, Mount Sinai Windreich AI & Human Health, BU Computational Biomedicine, UCSF BMI program /
   Bakar / Computational Precision Health, UCSF Bioengineering & Therapeutic Sciences, USF Bellini AI groups).
G3 molecular / biomedical homes: BME, Chemistry, Chemical Engineering, Pharmacology / Pharmaceutical Chemistry,
   Biochemistry, medical-school Biostatistics & Bioinformatics, comp-bio PhD programs, Genetics/Genomics, Radiology.
G4 NeuroAI: Neuroscience / Neurobiology / brain institutes.
Excluded: schools of public health; UCSF Epidemiology & Biostatistics; clinical departments other than Radiology.
Units in v3 are a starting list; add any G1–G4 unit at this school that v3 missed (check the school's official
departments pages for Chemistry, ChemE, Pharmacology, Mechanical/other engineering, Math). Also open the
2024–2026 "new faculty" news pages of the engineering school, CS/data-science school and medical school.

## Access
`python -m outreach.fetch` (hosts in config/browser_hosts.txt load in real Chromium automatically). If a host
refuses our UA but a normal browser loads it without a challenge, add the host to config/browser_hosts.txt.
Never work around a bot check / captcha / Cloudflare challenge; record `blocked` with the URL.
UCSF: departments come from UCSF Profiles (data/discovery/v3/ucsf_profiles_depts.json and
ucsf_profiles_scan.py); page through every result page.

## Per unit
1. Roster every rank page: `python -m outreach.roster --auto URL "<institution>" "<unit>" <slug>-<unit-slug>`;
   if 0 / wrong rows, write config/directories/<slug>-<unit-slug>.yaml (see cshl-faculty.yaml) and run it.
   Keep all ranks (filtering is done by code later). Titles verbatim. No LLM-typed names or titles.
2. Self-check: row count vs the page (state both numbers), 3 random rows vs the page, no students / staff.
   page_count is YOUR count of the live page, never the scouting number. (USF 2026-10-31: auto-parse silently
   dropped people whose card layout differed — EE 24/28, Chemistry 45/49 — and took "Google Scholar" /
   "Tampa Campus" as names. Search the page text for every surname you expect before declaring done.)
   Pagination without rel=next (Duke "page/2") is not followed: list every page URL in a YAML. Sidebar staff
   rows and badge text ("NAE Member") are not people. (Duke ECE lost 19 of 56 faculty this way.)
- Paginated search pages: check each page's 'of N' equals the unit total; a fallback page silently injects other departments (Mount Sinai 2026-10-31).
3. Big list without titles (e.g. names only): still roster it; titles come from profiles later.
Budget: ~90 tool calls. Cut losses on a unit after ~6 calls: mark it and move on.

## Output
Append one line per unit to data/grid/<slug>.jsonl:
{"institution","unit","group":"G1..G4","urls":[...],"roster":"data/roster/<file>.jsonl","rows":N,
 "page_count":N or null,"titles":true/false,"status":"done|blocked|js_only|none|skipped","note":"..."}
Reply ≤12 lines: per group the units and row counts, then problems / blocked URLs.
