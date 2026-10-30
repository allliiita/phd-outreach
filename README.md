# phd-outreach

Multi-agent system that builds a verified database of AI / ML / statistics / computational-biology faculty and institute PIs, and turns it into personalised, human-approved PhD outreach emails.

Built on the "trust first, then parallelise" approach: every stage has an independent verifier, deterministic checks sit underneath the agents, and each stage's autonomy is gated by its measured error rate.

| Path | What |
|---|---|
| `CLAUDE.md` | Coordinator instructions (read by Claude Code) |
| `HANDOFF_PROMPT.md` | What to paste into Claude Code to run it |
| `agents/` | Playbooks: department discovery, roster, profile, verifier, email writer, email critic |
| `outreach/schema.py` | Record schema; fields without verbatim sources are rejected |
| `outreach/validate.py`, `emailcheck.py` | Deterministic checks (domain, snapshot match, dedupe, banned phrases, …) |
| `outreach/fetch.py`, `papers.py` | Page fetching with snapshots; OpenAlex papers |
| `outreach/trust.py` | Per-stage trust levels and audit sampling |
| `outreach/pipeline.py` | merge / verdicts / status / export (xlsx) |
| `outreach/send.py` | Batches → Gmail drafts → human approval (TTY-only) → paced sending |
| `config/` | Institutions + email domains; applicant facts the writer may use |
| `data/pilot/` | Pilot run (CMU Statistics & Data Science, Broad Institute roster) |
| `tests/` | Unit tests for the check layer; gold-set scorer |
