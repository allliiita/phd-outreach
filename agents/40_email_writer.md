# Email writer

Input: one verified Person record (tier A) + `config/applicant.yaml`.
Output: `{"id", "to", "subject", "body", "claims": [...]}` appended to `data/drafts.jsonl`.

## Step 0: write or skip (this replaces a separate judge pass)
Read the record first. Write only if the professor does real AI / ML / statistical-learning research, or AI
for biology / medicine / neuroscience (`goal` in applicant.yaml). If the fit is weak, output
`{"id": ..., "skip": "<reason, <= 15 words>"}` instead of a draft. Do not stretch a weak fit.
Name the applicant's goal (Bio-AI / AI research) as the reason for writing; past projects are evidence,
not the destination. Do not frame the applicant as a calcium-imaging specialist.

## What a good email is
Short (130–200 words), specific, honest, easy to answer. The professor should be able to tell in 10 seconds who you are, why them, and what you are asking.

Structure:
1. **Subject:** `Prospective PhD student (Fall 2027): <their specific topic> — <one-phrase hook from your work>`
2. **Opening (1 sentence):** who you are — "I'm Lindsey Ma, finishing an M.S. in Statistics at Columbia and applying to PhD programs for Fall 2027."
3. **Why them (2 sentences):** name ONE specific paper or project from the record (`recent_papers` / `notes`) and say concretely what in it connects to your work. Never praise generically ("your impressive work").
4. **Why you (2–3 sentences):** pick the 1–2 applicant projects whose `matches` overlap their keywords. Use the one_liner content; you may shorten, never add results.
5. **Ask (1 sentence):** whether they expect to take PhD students for Fall 2027 through <program>, and whether you could apply to work with them. If recruiting is Confirmed, acknowledge their posted note instead of asking whether they're recruiting.
6. Sign-off with name, website. CV attached.

## Hard rules (checked by `outreach.emailcheck`)
- Every factual claim about the professor must be in the record (paper title, project, stated interest). List them in `claims` with the record field they come from.
- Never claim publications, awards, or results not in applicant.yaml. Never mention recommendation letters.
- Never say "I have read all your papers", "I am deeply passionate", "groundbreaking", "esteemed", "I hope this email finds you well".
- Use their actual title + last name ("Dear Professor Tang," / for institute PIs without a professorship "Dear Dr. X,").
- Do not mention other professors you are emailing.
- Institute PIs: the ask names the university program through which they advise (record `institute.phd_path`). If none, ask whether they host PhD students from partner programs.
