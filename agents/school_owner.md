# School owner (one school to a passing `python -m coverage.check --school "<School>"`)

Recipe from the Cornell pilot. Follow in order. First step: `git log -1` must be the SHA in your kickoff, else `git reset --hard <SHA>`.
You may write: `config/directories/<slug>-*.yaml`, `data/roster/<slug>-*.jsonl`, `data/grid/<slug>*.jsonl`, `data/coverage/`,
`coverage/`, `tests/`. Not: other schools, CLAUDE.md, config/targets.yaml, docs/decisions.tsv. Never hand-edit a roster row or a count.
Everything below is a command; counts are computed, not typed.

## 0. Baseline
`python -m coverage.ledger >/dev/null && python -m coverage.check --school "S"` lists the four sections (units, recall, funnel, unverified).
Unverified rows need `data/snapshots/` (gitignored, absent in the cloud): not yours; report the count.

## 1. Units (grid + census in data/grid/<slug>.jsonl / .units.jsonl)
For every census row decided covered/added, `grid_unit` must equal ONE grid row's `unit` string exactly (a `;` inside parentheses is part of the name).
- Same unit under another name: `python -m coverage.census_map --school S --from OLD --to GRIDNAME`.
- Not rostered: find the faculty page, `python -m outreach.roster --probe URL`, write `config/directories/<slug>-<unit>.yaml`
  (item/name/title/profile selectors; `urls:` as a block list in quotes when URLs contain `?`; `skip_titles` to drop staff),
  run `python -m outreach.roster config/directories/<file>.yaml`.
  Duffield engineering sites (ece, orie, bme, mae, sys) share selectors: item `li.ce-block__people-list-item`, name `p.ce-block__people-list-person-name`, title `p.ce-block__people-list-person-title`, profile `a.ce-block__people-list-item-link@href`.
  Staff filter that worked everywhere: `skip_titles: ['^(?!.*(professor|lecturer|instructor|scientist|faculty|chair|emerit)).+$']` (keeps only faculty-word titles).
- Count check: `python -m coverage.pagecount --yaml config/directories/<file>.yaml --roster data/roster/<slug>-x.jsonl`
  prints entries on the page, kept, dropped (READ the dropped list: staff/postdocs are fine, a real professor is a bug), and faculty missing from the roster.
  Tool-less pages: `python -m coverage.pagecount URL`. Duplicate cards on a page: page_count = unique people.
- Write the row: `python -m coverage.gridrow --school S --unit "NAME" --status done --roster data/roster/x.jsonl --page-count N --note "yaml, entries/kept/dropped"`.
  `rows` is counted from the roster file; `done` fails check unless rows == page_count.
- Mismatch causes seen: staff/postdocs on the page (record the true faculty count, not 0); a page that changed since the old roster
  (regenerate from YAML); stale auto-made rosters (`<school>-university-*.jsonl`) that outlived the YAML ones: delete them with `git rm` after diffing names (only staff were lost).

## 2. Blocked units: the alternates ladder (in order; record `--status alt --alt-source URL`)
1. Plain GET again: "blocked" notes from older runs were often transient (stat.cornell.edu worked). Try `python -m outreach.fetch URL` first.
2. Real browser: `outreach.fetch.get` renders SSL-failing hosts with Playwright; in the cloud container it is NOT installed (cs/infosci.cornell.edu stay dead). Do not pip-install browsers or bypass TLS.
3. Wayback `https://web.archive.org/web/2026/<url>`: resets from the cloud proxy (also WebFetch refuses it). Try once, move on.
4. College/graduate directory with a department filter: Cornell Bowers `https://bowers.cornell.edu/directory?department=15|16|17&page=N` (15 CS, 16 IS, 17 Stats) via `python -m coverage.bowers_dir` (bowers is in browser_hosts.txt, so use requests, not fetch.get). The unfiltered list omits people; a filter id is found in the form's `input[name=department]`.
   Weill: `https://gradschool.weill.cornell.edu/faculty?program=<id>` (ids in `select[name=program]`), table rows, no titles.
5. CSRankings for CS: `python -m coverage.csr_unit --school S` writes `<slug>-csrankings.jsonl` (used beside a partial directory; it found Wen Sun).
6. New-faculty news, NSF/NIH probes (already running in the recall check).
7. Only then `data/coverage/human_requests.jsonl` `{school, unit, url, why}` for the human to save the page.
A `.edu` host that answers `curl` with "unable to get local issuer certificate" is the SSL case in step 2.

## 3. Recall misses (probe hit not in the ledger)
Find WHY, in this order: (a) in a unit you have not rostered: fix section 1; (b) name mismatch (credential, initials, 29-char NSF cut-off,
nickname): fix the code with a test, or `--reason alias_of_ledger`; (c) person not in scope: `python -m coverage.explain --school S --name N --reason R --evidence URL`.
Reasons: moved_institution, senior_title, not_phd_advising_title, postdoc_pre_independent (NIH K99), clinical_unit, out_of_scope_unit, alias_of_ledger.
Evidence URL is a page you fetched (official page; NSF `api.nsf.gov/services/v1/awards/<id>.json`; `api.reporter.nih.gov/v2/projects/search`).
Never explain with "not ML" (fit judges decide). Young and in scope but unrostered: `python -m coverage.add_person --school S --name N --url PROFILE`.
Tip: NSF/NIH probe names may be spelled differently from the roster; check `grep -il surname data/roster/<slug>*.jsonl` before concluding "missing".

## 4. Funnel: empty titles
`python -m coverage.ledger && python -m coverage.titles --school S` reads each untitled in-scope person's profile page and appends
`data/coverage/titles.jsonl` (survives re-scrapes; ledger applies it). Printed leftovers have no title on their page: look them up on an
official page and record with `--set NAME --title T --url URL`. Then rerun `coverage.ledger`. Open people who are young + in scope remain for the fit judges.

## 5. Finish
`python -m pytest -q tests | tail -1`; `python -m coverage.check --school S`; commit on your branch (end message with the attribution lines). Report <=12 lines:
SHA, per-unit done/alt + source, explained count by reason, people added, remaining open (funnel names), human requests, tool/code fixes with their tests.
Any bug you meet in a stage gets a failing test first (tests/test_<school>_pilot.py style); never fix a record by hand.
