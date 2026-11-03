# School owner (one school to a passing `python -m coverage.check --school "<School>"`)

Recipe from the Cornell pilot. Follow in order. First step: `git log -1` must be the SHA in your kickoff, else `git reset --hard <SHA>`.
Standing overrides (every kickoff): you NEVER edit shared code (`coverage/`, `outreach/`, `tests/`): report the bug (file, repro command, expected) in your reply; the single code worker fixes it. The real browser (Chromium via Playwright) IS available: `python -m outreach.fetch URL --render`.
You may write: `config/directories/<slug>-*.yaml`, `data/roster/<slug>-*.jsonl`, `data/grid/<slug>*.jsonl`, `data/coverage/`.
Not: other schools, CLAUDE.md, config/targets.yaml, docs/decisions.tsv. Never hand-edit a roster row or a count.
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
- Write the row (`--status done` is REFUSED when roster rows != page_count and prints the diff: fix the roster/YAML or the count source first; use `found`/`blocked` meanwhile): `python -m coverage.gridrow --school S --unit "NAME" --status done --roster data/roster/x.jsonl --page-count N --note "yaml, entries/kept/dropped"`.
  `rows` is counted from the roster file; `done` fails check unless rows == page_count.
- Mismatch causes seen: staff/postdocs on the page (record the true faculty count, not 0); a page that changed since the old roster
  (regenerate from YAML); stale auto-made rosters (`<school>-university-*.jsonl`) that outlived the YAML ones: delete them with `git rm` after diffing names (only staff were lost).

## 2. Blocked units: the alternates ladder (in order; record `--status alt --alt-source URL`)
1. Plain GET again: "blocked" notes from older runs were often transient (stat.cornell.edu worked). Try `python -m outreach.fetch URL` first.
2. Real browser: `python -m outreach.fetch URL --render` (headless Chromium). The requests path trusts the proxy CA plus `config/extra_ca/*.pem` (emSign root: InCommon .edu hosts such as cse.ucsd.edu, cs.umd.edu, cs.cornell.edu now load). Errors name the layer: `[tls]`, `[browser]`, `[http]`, `[network]`. Never bypass TLS.
3. Wayback `https://web.archive.org/web/2026/<url>`: resets from the cloud proxy (also WebFetch refuses it). Try once, move on.
4. College/graduate directory with a department filter: Cornell Bowers `https://bowers.cornell.edu/directory?department=15|16|17&page=N` (15 CS, 16 IS, 17 Stats) via `python -m coverage.bowers_dir` (bowers is in browser_hosts.txt, so use requests, not fetch.get). The unfiltered list omits people; a filter id is found in the form's `input[name=department]`.
   Weill: `https://gradschool.weill.cornell.edu/faculty?program=<id>` (ids in `select[name=program]`), table rows, no titles.
5. Probes (CSRankings / NSF / NIH) are leads, never roster rows (a CSRankings roster once added Wen Sun, who had left). Confirm each lead on a CURRENT official page or the person's own current homepage; the ledger ignores probe-sourced rosters.
6. New-faculty news, NSF/NIH probes (already running in the recall check).
7. Only then `data/coverage/human_requests.jsonl` `{school, unit, url, why}` (add `name` for a person) for the human to save the page. `coverage.check` shows these in a "waiting on human" column, not as open work; the unit stays non-terminal (exit 1) until the page arrives.
A `.edu` host that answers `curl` with "unable to get local issuer certificate" is the SSL case in step 2.

## 3. Recall misses (probe hit not in the ledger)
Find WHY, in this order: (a) in a unit you have not rostered: fix section 1; (b) name mismatch (credential, initials, 29-char NSF cut-off,
nickname): fix the code with a test, or `--reason alias_of_ledger`; (c) person not in scope: `python -m coverage.explain --school S --name N --reason R --evidence URL --quote "verbatim text from that page" [--unit U|--to INST|--title T] [--dry-run]`.
The tool fetches the page and REFUSES unless the quote is on it; the row stores quote + fetch date. Rows without a verified quote (all legacy ones) do not count in `coverage.check`: they show as "unproven exclusion". `--validate --school S` re-checks stored rows.
Past-title rule: a stored title must be current. A page that says "was", "formerly", "prior to" is not evidence (`coverage.titles` rejects it); a person whose page says they now work elsewhere is `moved_institution`.
Reasons and what each needs: moved_institution (`--to`: full name or any alias, named in the quote); senior_title / not_phd_advising_title (`--title`); all three quotes must also contain the person's surname;
clinical_unit / out_of_scope_unit (`--unit`, in the quote; an official page naming the department, NOT nsf.gov / nih.gov APIs; out_of_scope is REFUSED for engineering / CS / ECE / statistics / data / applied math / OR / information / linguistics units); alias_of_ledger (`--note "same as <ledger name>"`, no fetch);
postdoc_pre_independent (evidence = the person's NIH RePORTER project; the tool queries RePORTER: an active K99, fiscal year >= current FY-1, at this school, and NO R00 for the PI; otherwise refused; the refusal names the R00's organization: use moved_institution, or add_person if in scope. A stale K99: probably faculty, look for the new post).
Never explain with "not ML" (fit judges decide). Young and in scope but unrostered: `python -m coverage.add_person --school S --name N --url PROFILE`.
Tip: NSF/NIH probe names may be spelled differently from the roster; check `grep -il surname data/roster/<slug>*.jsonl` before concluding "missing".

## 4. Funnel: empty titles
`python -m coverage.ledger && python -m coverage.titles --school S` reads each untitled in-scope person's profile page and appends
`data/coverage/titles.jsonl` (survives re-scrapes; ledger applies it). Printed leftovers have no title on their page: look them up on an
official page and record with `--set NAME --title T --url URL`. Then rerun `coverage.ledger`. People still without a rank show outcome `open:title` in the check detail (not fit-pending, no card is made until a title exists). Young + in scope + titled people remain for the fit judges. Named / endowed chairs, "Distinguished", "Professor and ..." are NOT young even next to "Associate Professor".

## 5. Finish
`python -m pytest -q tests | tail -1`; `python -m coverage.check --school S`; commit on your branch (end message with the attribution lines). Report <=12 lines:
SHA, per-unit done/alt + source, explained count by reason, people added, remaining open (funnel names), human requests, tool/code fixes with their tests.
Any bug you meet in a stage gets a failing test first (tests/test_<school>_pilot.py style); never fix a record by hand.
