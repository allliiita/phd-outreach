# Prompt for the next agent (paste into Claude Code on your own computer, inside this repo)

```
You are rebuilding batch 1 of my PhD-outreach professor list. Read docs/REQUIREMENTS.md first; it is the
source of truth (what I want, who counts, the mistakes made so far, the deliverable). Then skim CLAUDE.md,
config/targets.yaml, docs/cshl_bioai.md, and the existing tools in outreach/ (fetch.py saves page snapshots
and extracts emails incl. obfuscated ones; roster.py scrapes a directory from CSS selectors or --auto;
enrich.py fills email/homepage/research text/papers for roster rows; validate.py checks emails and quotes
against saved snapshots). Reuse them; do not reinvent.

Work target-first, as a grid:
1. Build the grid: for each school in config/targets.yaml, list every department / institute of types T2–T8
   from the school's official "departments" pages (medical school, engineering, arts & sciences, institutes).
   Use one subagent per school in parallel. Each subagent returns rows
   {school, department, type, faculty-list URL(s)} and an explicit status per type
   (found / none at this school / blocked / not found + what it checked). Show me the grid before step 2.
2. For each department, take the COMPLETE official faculty list (every rank page), with titles verbatim.
   If a site blocks scripts, open it in the browser and save the page to data/snapshots/manual/.
   Verify each roster: count matches the page, 3 random rows correct, no students/staff/emeritus.
3. Keep young faculty (Assistant / Incoming Assistant / Associate since ~2020) with Chinese surnames.
   Anyone on an official page counts, even with no papers.
4. Enrich (email verbatim from an official page, homepage, one-line research summary, 1–2 recent papers if
   found). Run validate.py. No email found -> list them separately; never construct an address.
5. An independent auditor agent (different model, agents/60_auditor.md) checks a sample and the coverage
   sheet before I see the result.
Deliver data/export/batch1.xlsx (people + coverage sheet). Ask me only for logins and borderline calls.
Existing data from earlier runs (data/roster, data/dossiers, data/people, data/export/batch1.xlsx) may be
reused where a department's official list was actually scraped; treat paper-derived rows (ps-*) as hints only.
```
