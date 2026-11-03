# Email writer

Input (file paths, do not paste): `data/email/packs/<id>.json` (one fact pack) + `config/applicant.yaml`.
Output: `data/email/drafts/<id>.json` = `{"id", "to", "subject", "body", "claims": [{"para", "text", "source"}]}`.
Then run `python -m outreach.emailcheck <id>` and fix every reason it prints (max 2 rounds). Do not edit the pack.

## Sources (the only facts you may use)
- About the professor: the pack only (`papers[i].title/year/coauthors/venue`, `research.text`, `keywords`, `units`, `title`, `recruiting`).
  If a fact is not in the pack, it is not in the email. Do not use memory, the web, or the abstract of a paper.
- About the applicant: `config/applicant.yaml` only (`degree`, `interests`, `goal`, `projects[].one_liner`). Shorten, never add results.
  Never claim publications, awards, or numbers not in the file. Never mention recommenders or recommendation letters.
- If `matched_projects` has `weak: true` entries, prefer the other projects in applicant.yaml whose one_liner fits the paper honestly;
  if none fits, write the connection as a question of method (what you did), not as shared subject matter.

## Format (fixed by the applicant; the checker enforces it)
Subject: `PhD Inquiry – <Applicant Name> – <Topic of this professor>` (en dashes; topic from pack research/keywords, 3-8 words).
Body = `Dear <pack.salutation>,` then exactly 6 paragraphs, then `Sincerely,` newline `<Applicant Name>`. Paragraphs separated by one blank line.
1. "I am <name>, a prospective PhD applicant interested in <2-3 interests tied to this professor>. I hold <degree(s)> and have since focused on <relevant work>."
2. "I recently read your <year> paper "<exact title>" (<co-authors/venue if in the pack>). I was particularly interested in <one specific idea in it>. This resonated with my experience <one applicant project>."
   The title is copied character for character from `papers[i].title`, in quotation marks. The "specific idea" must be derivable from the title or
   `research.text`; if the pack gives no more than the title, name the idea the title itself states and nothing deeper. Optionally one more pack item (second paper, a recruiting note).
3. "My broad research interest lies in <...>. More specifically, I am interested in <...>. I see this as a direction I would like to develop further under supervision."
4. 2-3 sentences of concrete evidence from a DIFFERENT applicant project than paragraph 2, then:
   "I would be interested in learning how your research group approaches <...>. Would you be considering PhD students for 2027 entry?"
5. "My CV and selected project portfolio are attached for your reference. I would be happy to share my academic transcript and a research concept note upon request."
6. "Thank you for your time and consideration. I would appreciate the opportunity for a brief discussion if my research interests might be relevant to your ongoing work."
Paragraphs 1-6 total 230-330 words.

## Claims
Every sentence of paragraphs 1-4 that states something about the professor or the applicant has a claim:
`{"para": 2, "text": "<the claim in your words>", "source": "<path>"}` where path is a pack field (`papers[0].title`, `research.text`, `keywords`, `units`)
or an applicant field (`applicant.degree`, `applicant.interests`, `applicant.projects.<key>`). Paragraph 2 needs a `papers[i]` claim;
paragraphs 2 and 4 each need an `applicant.projects.<key>` claim and the keys differ.

## Be specific or say less
The email must contain at least 2 words from the pack (research terms, paper concepts) that would not fit any other professor; the checker's swap test fails otherwise.
If the pack is too thin to do that honestly, write `{"id", "skip": "<reason, <= 15 words>"}` to `data/email/drafts/<id>.json` instead of padding.

## Banned
"I hope this email finds you", "deeply passionate", "groundbreaking", "esteemed", "renowned", "I have read all", "your impressive work",
"your inspiring work", "delve", "tapestry", "cutting-edge", "state-of-the-art", "world-class", "I am writing to express my", any mention of recommenders,
"my publication", "my paper". No flattery, no mention of other professors, no claim that the applicant is a calcium-imaging specialist
(goal: AI/ML methods research; bio/neuro applications welcome; past projects are evidence, not the destination).
