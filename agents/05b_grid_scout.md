# Grid scout addendum (batch 1 rebuild, 2026-10-31) — read after 05_department_discovery.md

You build ONE school's row of the grid (school × unit type T2–T8). Repo: /home/user/phd-outreach
(run commands from there). Read docs/REQUIREMENTS.md "Who counts" first. Your earlier-run file
data/discovery/v2/<slug>.jsonl is a starting hint: re-open every URL in it, do not copy it blindly.

## Access rules (the cloud IP is walled by Akamai/Cloudflare at UCSF, UMich, Penn Medicine/SEAS, Mount Sinai)
Allowed, in this order:
1. `python -m outreach.fetch URL [--links|--emails]` (saves snapshots; falls back to headless Chromium).
2. Official alternative hosts of the SAME school that are not walled, e.g. UCSF Profiles
   (profiles.ucsf.edu — official directory, searchable by department/title), Mount Sinai Scholars
   (scholars.mssm.edu), department sites on other subdomains, the school's PhD-program faculty pages.
3. Internet Archive copy of the official page (`https://web.archive.org/web/2026/<url>`) — only to learn
   unit names and faculty-list URLs; mark `"via":"wayback:<timestamp>"`. Archive copies are not used as
   roster sources if they are older than 2026-01.
4. WebSearch only to find entry pages / URLs (≤8 searches). Snippets can suggest a unit exists; mark such
   rows `"verified": false`.
NOT allowed: third-party fetch/reader/scraping proxies or any attempt to get past a bot check or captcha.
If a page is walled, record it as `blocked` with the exact URL — the applicant will open those in her own
browser and save them to data/snapshots/manual/. A clean list of blocked URLs is a useful result.

## Scope reminders
- Types: T2 biomed informatics / data science / AI in medicine; T3 comp bio / bioinformatics / systems bio /
  genomics (computational faculty; medical-school biostatistics & bioinformatics departments count here);
  T4 statistics & data science (NOT public-health biostatistics); T5 BME; T6 data-science institutes with own
  faculty; T7 computational neuroscience / neuroscience; T8 CS/ECE (Bio-AI faculty only).
- Also look for cross-department homes of young comp faculty: interdisciplinary PhD programs (e.g. a
  "Computational Biology PhD program faculty" page), new AI/data institutes with joint hires, and
  "new faculty" / "welcome our new faculty" news pages 2024–2026 (incoming assistant professors are often
  only listed there).

## Output: write data/discovery/v3/<slug>.jsonl
One line per (unit, faculty-list page):
{"institution","unit","type","url","rank_pages":[...] (if the list is split by rank),
 "filter":"all|ml_only|bioai_only","status":"ok|blocked|js_only|no_list",
 "parse":"auto:<rows>|yaml:<path>|none","shows_titles":true/false,"approx_faculty":N,
 "via":"direct|alt-host|wayback:<ts>|search","verified":true/false,"source":"<list page it came from>",
 "note":"..."}
Last line: {"_coverage":{"T2":{"status":"found|none|blocked|not_found","units":[...],"checked":[...urls...],
 "why":"..."}, ... "T8":{...}}}
Status meanings: found = ≥1 unit with a readable official faculty list; none = you read the school's official
unit lists and no such unit exists; blocked = the unit exists but its pages are walled (give URLs);
not_found = could not tell (say what you checked).
Budget: ~60 tool calls. Do not scrape rosters fully or enrich people — that is step 2.
Reply in ≤12 lines: one line per type `Tn: status — units (approx faculty) [via]`, then the blocked URLs.
