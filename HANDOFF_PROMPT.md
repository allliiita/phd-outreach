# Paste this into Claude Code on your computer (inside the unzipped `phd-outreach` folder)

```
You are running my PhD-outreach system in this folder. Read CLAUDE.md, then agents/00_rules.md, and follow them exactly — they define the coordinator / stage-manager / worker / verifier hierarchy, the trust pyramid, and the sending rules.

Setup (do now, report results):
1. python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python -m pytest -q
2. Smoke-test the network tools: python -m outreach.fetch https://www.cmu.edu/dietrich/statistics-datascience/people/faculty/index.html --emails | head ; python -m outreach.papers "Weijing Tang" "Carnegie Mellon University"
3. Move the pilot data in: mkdir -p data/people data/verdicts && cp data/pilot/people_*.jsonl data/people/ && cp data/pilot/verdicts_*.jsonl data/verdicts/ ; then python -m outreach.pipeline merge && python -m outreach.pipeline verdicts && python -m outreach.pipeline status
   Re-run the pilot people through outreach.fetch so data/snapshots holds the real pages, and re-run merge: from now on every email and quote is checked against saved bytes.

Then work through CLAUDE.md "Order of work":
- Pilot = CMU Statistics & Data Science (already rostered) + Broad Institute (rostered) + one more institution of your choice. Show me every pilot record in a table before scaling; I will correct some, and you turn each correction into a validate.py check or a playbook line.
- Build tests/gold/people.jsonl from the 30 records I approve, and pass tests/score_gold.py before scaling.
- Then all institutions in config/institutions.yaml, departments → roster → profile → verify, 5–10 subagents in parallel. Prioritise departments in this order: Statistics, Biostatistics, Computational Biology / Biomedical Informatics, Data Science, CS (ML/CV/NLP/AI-for-science faculty), ECE/OR/Applied Math/Neuroscience (ML faculty only), institutes.
- Start the email stage as soon as ~100 verified tier-A records exist; early-career faculty first. Writer and critic must be different subagents (critic on a different model if available). Run outreach.emailcheck on every draft.
- Sending: create batches of 20 (python -m outreach.send batch), put them into Gmail as drafts (send drafts N) and tell me. I review and either send from Gmail or run `send approve N` myself in a terminal, after which you may run `send send N`. Never more than 40/day. If Gmail OAuth needs a login, pop the browser and wait for me.

Every evening append to data/LOG.md: counts by stage, verifier pass rate per stage, errors found, and which new check prevents each. Ask me only for logins, batch approvals, and borderline-relevance calls (collect those into one list).
```

Before you paste it:
- Put your CV PDF at `assets/Lindsey_Ma_CV.pdf` (export the CV doc as PDF).
- Check `config/applicant.yaml` (sender address, project one-liners).
- For Gmail sending: Google Cloud Console → create project → enable Gmail API → OAuth client (Desktop) → download as `secrets/credentials.json`. The agent can walk you through it.
