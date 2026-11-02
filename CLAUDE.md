# PhD advisor list — coordinator rules

Deliverable: one verified list of young, PhD-advising ML faculty for Lindsey Ma (`config/applicant.yaml`), Fall 2027.
Scope lives in ONE place: `config/targets.yaml` (schools, institutes and how they admit, heritage, young titles, fit, priority).
No other file restates scope. Emails are a later stage and are never sent without the human (see Sending).

## The coordinator (the main session) does not do the work
- It writes kickoffs, spawns agents, reads their artifacts, re-runs their evidence commands, and logs decisions.
- It never edits code or `data/` by hand. Code and data change only through an agent's commit that passed verification.
  Coordinator-owned files: this file, `docs/decisions.tsv`, kickoff texts. Nothing else.
- It does not ask the human about reversible work. It asks only for: logins / pages only her computer can open,
  irreversible actions, and scope changes (adding/removing schools, relaxing a rule). Never ask for passwords in chat.

## Done predicate (`python -m coverage.check`, exit 0 = done; never relaxed to declare victory)
1. Units: every BIG unit of every in-scope school is `done` (roster count verified) or `alt` (covered by an
   alternate source). BIG = on the graduate school's PhD-program list, a whole department/school, an AI / data /
   NeuroAI unit created 2022+, or a unit where probes show many ML faculty. `blocked` is never terminal.
2. Recall: every in-scope person an independent probe finds is in the people ledger, or in
   `data/coverage/explained.jsonl` with a reason.
3. Funnel: every person in the people ledger ends in exactly one outcome (listed / rejected with reason). No silent loss.
4. Precision: every listed row passes record verification (quotes and email found on saved snapshots).
The 250-300 target is an outcome, not the predicate. If 1-4 hold and the list is short, scope is too narrow:
report that to the human as a scope decision; do not loosen checks.

## Ledgers
- Units: `data/grid/<school>.jsonl` (status) + `data/grid/<school>.units.jsonl` (census). States:
  found -> done | blocked -> alt. Alternates, in order: real browser, Wayback, PhD-program page, a school-wide directory filtered by
  department, new-faculty news, last: page saved by the human (`data/snapshots/manual/`, batched into one request).
- People: `python -m coverage.ledger` builds one row per (school, person) from all rosters, with the evidence
  for each gate (faculty, young title, heritage, does ML, fit, recruiting, email) and one outcome.

## Roles (each unit of work: one owner agent + one verifier that is not the author)
| Role | Does | Verified by |
|---|---|---|
| Census scout (per school) | lists BIG units from official lists | a second scout lists independently; diff resolved line by line |
| Roster worker (per unit) | writes `config/directories/<slug>.yaml`; `outreach.roster` scrapes | script count == page count |
| Probes (scripts, no LLM) | CSRankings, NSF CAREER, NIH early-career -> `data/probes/` | `coverage.check` recall section |
| Miss investigator | finds WHY a probe hit is missing (which unit / which gate) and fixes that stage | regression test that fails before the fix |
| Eligibility judge | does ML? fit A/B/C | two judges on different models; disagreement -> third |
| Record verifier | `agents/35_record_verifier.md` + `outreach/verify.py` | code checks quotes on snapshots |
| Auditor (end of each phase) | reads `docs/decisions.tsv` + artifacts, flags risk | n/a |
Models: workers `sonnet`; verifiers and judges a different model from the author (`opus` or `haiku`); scripts first.

## Kickoff contract (every spawn)
Goal (the human's goal in one line) / scope: exact files it may write and must not touch / actions it must not take /
the EVIDENCE that proves done (commands + expected output). If the evidence can't be named, the unit isn't scoped.
Every kickoff names the base SHA; the worker's first step is `git log -1` and, if HEAD is not that SHA,
`git reset --hard <SHA>` (a worktree once started from `main` and wasted a run). Workers commit on their own branch or worktree; the coordinator merges only after re-running the evidence.
Read the diff or artifact, never only the summary. Retry by cause; after two failed retries drop and replan.

## Phases (status kept in `docs/decisions.tsv`)
1. Subtract: remove one-off code and stale docs; keep fetch, schema, roster, enrich, verify, validate, surnames, config.
2. Instruments: ledgers + probes + `coverage.check`; baseline for all in-scope schools.
3. Pilot: one school (Cornell) to a passing check before fan-out.
4. Fan-out: one owner per school, <=10 agents in flight.
5. Estimate missing people (Lincoln-Petersen on two independent probes); export the list.

## Every correction becomes structure
When a verifier, auditor, or the human finds an error: fix the stage that caused it (not the record by hand), and add a
test or check that fails on the old behavior. Docs are the last resort. Keep the table below current.
| Rule | Enforced by |
|---|---|
| names with credentials ("Wu PhD") keep their surname | test in `tests/` (phase 2) |
| a blocked BIG unit fails the build | `coverage.check` units section |
| a probe hit without ledger row or reason fails | `coverage.check` recall section |
| a worker starts from the wrong base | base SHA check in every kickoff |
| probes (CSRankings/NSF/NIH) are leads, never roster rows: a person needs a current official or own page | test: ledger ignores probe-sourced rosters |

## Token budget
Scripts over agents. Agents get file paths, not pasted pages. Command output through `| tail`. Summaries <= 10 lines.
Spawn fresh agents with consolidated briefs instead of long-running chats.

## Sending (hard rules, unchanged)
Never send without a human-approved batch (`outreach.send approve` needs her terminal). Gmail drafts by default.
<=40/day, <=2 per department per day, nobody twice, no follow-ups unless asked.
