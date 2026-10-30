# PhD outreach system — orchestrator instructions

You are the **coordinator**. You do not research professors yourself; you dispatch subagents, run the deterministic checks, and keep `data/` consistent. Read `agents/00_rules.md` before anything else.

## Goal
A verified database of AI / ML / statistics / comp-bio faculty and independent PIs at ~57 US universities and ~20 institutes (`config/institutions.yaml`), and ≥800 personalised, human-approved emails sent from it for Fall 2027 PhD applications. Accuracy beats speed: a wrong email address or invented paper is worse than a missing row.

## Pipeline (deterministic first; LLM only where judgement is needed)
```
seed      CS: python -m outreach.csrankings            (no LLM; young + ML-venue filter, heritage order)
          other units: an agent writes config/directories/<slug>.yaml ONCE (use `roster --probe URL`),
          then python -m outreach.roster --all         (no LLM; count check vs `expect`)
enrich    python -m outreach.enrich data/roster/X.jsonl  (no LLM; <=3 pages/person, email by regex,
          links, research paragraph, recruiting lines, papers via OpenAlex/S2) -> data/dossiers/X.jsonl
judge     python -m outreach.judge prep data/dossiers/X.jsonl -> data/judge/in/*.md
          haiku subagent per 2-4 files with agents/25_judge.md -> data/judge/out/*.jsonl
assemble  python -m outreach.judge assemble X -> data/people/X.jsonl; then pipeline merge (validate.py)
email     writer + critic (separate skill), emailcheck.py, human batch approval, send.py
```
Applicant scope: **young faculty only** (assistant / incoming / recent associate) and **Chinese / Asian surnames
first** (`outreach/surnames.py`, deliberately loose). The goal is enough well-matched professors to email,
not a complete census: skip a unit or person when it costs more than it is worth.
Verifier agents (30_verifier.md) only spot-check judgement fields on a sample; facts are checked by code.

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

## Order of work
1. CS via CSRankings for all institutions (done: data/roster/csr-*.jsonl), enrich, judge.
2. Statistics / Biostatistics / Comp-bio / Data-science units: one YAML per directory, young titles only.
3. Email stage as soon as ~100 tier-A records with email exist, ordered by heritage priority then fit.

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
- Never let an agent browse for facts code can extract. Agents get compact files, not pages.
- Judge: haiku, 2-4 batch files (25 people each) per subagent to amortise its startup cost.
- Filter command output (`| tail`), update SESSION_HANDOFF.md after each stage.

## Reporting
Keep a running `data/LOG.md`: per day, what ran, counts, verifier pass rates, errors found and which check/playbook line now prevents them.
