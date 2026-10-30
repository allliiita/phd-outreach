# Session handoff (2026-10-30)

State:
- Code: outreach/{schema,validate,fetch,papers,trust,pipeline,emailcheck,send}.py; tests pass (pytest -q).
- Playbooks: agents/00..50. Coordinator spec: CLAUDE.md. Run prompt: HANDOFF_PROMPT.md.
- Pilot data: data/pilot/roster_cmu_stat.jsonl (46), roster_broad.jsonl (736), people_cmu_{0,1,2}.jsonl (29, validator-clean). Verdicts incomplete.
- CV: Claude Docs "Lindsey Ma — CV (PhD Applications)". No rec-letter mentions in emails.

Decided next (not yet built):
1. Deterministic-first: seed CS faculty from CSRankings CSV; per-directory YAML scraper written once by an agent, run by code, checked by count; emails by regex from raw HTML; papers by OpenAlex; LLM only for relevance / keywords / recruiting quote / email writing.
2. Must run on user's machine (this cloud sandbox blocks university sites + OpenAlex).
3. Use pilot 29 CMU records as gold set.

Token rules: workers on Sonnet/Haiku, coordinator reads summaries only, filter command output, /clear between stages using this file.
