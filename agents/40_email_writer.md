# Email writer

Input: data/email/cards/<id>.json (facts + match, from agents/38_prof_reader.md) and config/applicant.yaml.
Output: one line in data/drafts.jsonl: {"id", "to", "subject", "body", "claims": [{"text", "card_field"}]}.
Skip (no draft) if the card's match is {"skip": ...}.

Follow the skeleton and template in docs/email_playbook.md exactly (230-300 words):
subject in their words -> who I am, their vocabulary -> the paper (exact title, co-authors, year) and its core idea
in my own words -> my ONE finding and the bridge -> my concrete question, "under your supervision" -> 1-2 other
projects as evidence + "Would you be considering PhD students for Fall 2027 through <program>?" -> CV attached,
brief conversation -> signature.

Rules:
- Every statement about the professor comes from the card; list it in `claims` with its card field.
- Every statement about Lindsey comes from applicant.yaml projects; shorten, never add numbers, results or titles.
- Each project appears once. No publications, no recommenders, no other professors.
- If contact_rule asks for a keyword or subject line, use it.
- "Dear Professor <Last>," (institute PI without a professorship: "Dear Dr. <Last>,").
- Plain, confident, specific. No flattery ("impressive", "esteemed", "groundbreaking"), no "I hope this email finds
  you well", no "deeply passionate", no "I have read all your papers".
