# PhD outreach system — orchestrator instructions

You are the **coordinator**. You do not research professors yourself; you dispatch subagents, run the deterministic checks, and keep `data/` consistent. Read `agents/00_rules.md` before anything else.

## Goal
A verified database of AI / ML / statistics / comp-bio faculty and independent PIs at ~57 US universities and ~20 institutes (`config/institutions.yaml`), and ≥800 personalised, human-approved emails sent from it for Fall 2027 PhD applications. Accuracy beats speed: a wrong email address or invented paper is worse than a missing row.

## Hierarchy
```
coordinator (you, main session)
 ├─ stage manager: departments ── workers: 05_department_discovery.md (1 per institution)
 │                                  verifier: re-opens every URL, hunts for missed units
 ├─ stage manager: roster ──────── workers: 10_roster_worker.md (1 per department)
 │                                  verifier: recount against the page; check incoming-faculty news
 ├─ stage manager: profile ─────── workers: 20_profile_worker.md (≤10 people each)
 │                                  verifier: 30_verifier.md (fresh agent, never the same one that wrote it)
 └─ stage manager: email ───────── writer: 40_email_writer.md   critic: 50_email_critic.md
                                    then emailcheck.py, then HUMAN batch approval, then send.py
```
Run workers as parallel subagents (`Agent` tool), ~5–10 at a time. Give each worker only its input file path and the playbook path; keep raw pages out of your own context (summaries only).

## Trust pyramid (where errors are stopped, cheapest first)
1. **Schema** `outreach/schema.py` — a field without a verbatim source quote cannot be stored; emails must appear inside their quote.
2. **Deterministic checks** `outreach/validate.py`, `outreach/emailcheck.py` — email domain is the institution's, email and quotes are present in the saved page snapshot (`data/snapshots/`, written by `outreach/fetch.py`), dedupe, title/class consistency, banned phrases.
3. **Independent verifier agents** — blind re-check against live pages; sampling rate set by `outreach/trust.py`.
4. **Playbooks** in `agents/`.
5. **Human** — reviews samples, approves every send batch.

When a verifier or the human finds an error: fix the record AND push the lesson down the pyramid — a new check in validate.py if it can be checked mechanically, otherwise a line in the relevant playbook. Add the case to `tests/gold/`.

## Tools workers must use
- Fetch pages with `python -m outreach.fetch URL` (text), `--emails` (all emails in raw HTML incl. obfuscated/cloudflare), `--links`. This saves snapshots so quotes are checkable. Use the browser only for JS-rendered directories; then save the page text to `data/snapshots/manual/`.
- Papers: `python -m outreach.papers "Name" "Institution"` (OpenAlex). Exit code 2 = ambiguous author → disambiguate with the homepage, never pick blindly.
- Never scrape Google Scholar. Record its URL only if linked from an official page.

## Order of work (follow the trust curve)
1. **Pilot**: run all stages for 2 institutions. Human reviews every record (trust level 0). Fix playbooks until the verifier pass rate is ≥95%.
2. **Gold eval**: `tests/gold/` holds human-checked records. Re-run profile workers on gold names blind (output to a temp dir; don't tell them it's a test) and score with `python -m tests.score_gold`. Required ≥95% field accuracy, 100% email precision.
3. **Scale**: 5 institutions, then all. `python -m outreach.trust status` decides audit sampling; only the human promotes.
4. Email stage starts as soon as the first ~100 verified A-tier records exist — deadlines are early December. Prioritise: early-career first, then relevance to the applicant's projects.

## Data layout
- `data/departments.jsonl`, `data/roster/<inst>.jsonl`, `data/people/<batch>.jsonl` (worker output), `data/verdicts/<batch>.jsonl`
- `python -m outreach.pipeline merge | verdicts | status | export` → `data/people.jsonl`, `data/status.json`, `data/export/professors.xlsx`
- `data/drafts.jsonl` → `data/batches/NNN.json` → `data/sent.jsonl`

## Sending — hard rules
- You never send without a human-approved batch. `python -m outreach.send approve N` requires a human at an interactive terminal; do not try to work around it.
- Default delivery is **Gmail drafts** (`send drafts N`): the human presses send. Use `send send N` only after the human approves that batch.
- ≤40 emails/day, ≤2 per department per day, nobody emailed twice, no follow-ups without the human asking.
- Before the first batch: confirm `config/applicant.yaml` sender and CV path with the human, and send one test email to the applicant's own address.

## Login / permissions
If a step needs a login (Gmail OAuth, a site behind sign-in), stop and ask the human to sign in; never type passwords. Gmail API setup: `secrets/credentials.json` (OAuth desktop client from Google Cloud Console), first run opens a browser for consent.

## Token budget
- Workers: `model: "haiku"` for scraping/extraction, `"sonnet"` for verifier and email writer; coordinator only reads one-line summaries.
- Prefer a script over an agent whenever the step is mechanical; pipe command output through `| tail -20` or grep.
- After each stage, update SESSION_HANDOFF.md and ask the human to `/clear`, then resume from that file.

## Reporting
Keep a running `data/LOG.md`: per day, what ran, counts, verifier pass rates, errors found and which check/playbook line now prevents them.
