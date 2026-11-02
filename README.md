# phd-outreach

Builds one verified list of young, PhD-advising ML faculty for a Fall 2027 applicant. Emails are a later
stage and are never sent without a human-approved batch.

- Rulebook, scope, done predicate and roles: `CLAUDE.md` (read first).
- Scope config: `config/targets.yaml`; applicant facts: `config/applicant.yaml`.
- Worker playbooks: `agents/`. Code: `outreach/` (fetch, roster, enrich, verify, validate, ...), `coverage/`.
- Decision log: `docs/decisions.tsv`. Background: `docs/coverage_logic.md`.
- Tests: `python -m pytest -q tests`.
