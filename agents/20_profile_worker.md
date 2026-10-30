# Profile worker

Input: a list of roster rows `{name, institution, department, title_on_roster, roster_url, profile_url}`.
Output: one JSON object per person (JSON Lines) matching `outreach/schema.py::Person`.

For each person:
1. Open the department profile page. Copy the title verbatim → `position` (with quote + url). Map to `position_class`.
2. Find the email on that page or on the person's homepage. Copy with quote. If none → `"email": null`.
3. Follow links to the personal homepage, lab site, CV, Google Scholar. Record URLs only if the link is actually on a page you opened.
4. On the homepage, read the research description. Extract 3–8 specific keywords (e.g. "conformal prediction", not "machine learning"), and set `keywords_evidence` to a sentence from that description.
5. Look for: start year ("joined in 2024", CV entry), recruiting statements ("I am recruiting PhD students for Fall 2027"), new-lab statements. Quote them.
6. Get 1–3 papers from the last 3 years: prefer the homepage publication list or the OpenAlex/Semantic Scholar API. Copy titles exactly; give a URL (doi, arxiv, or venue page).
7. Put 2–4 short, sourced facts useful for a personalised email in `notes`: current project names, a recent talk, a stated interest in students with statistics/neuroscience/biology backgrounds. Format: `fact (url)`.
8. Set `tier`: `A` if relevance is yes/borderline and position_class is assistant/incoming_assistant/associate/full/institute_pi/research_faculty; else `B`. For B tier, steps 4–7 are optional.

Record template:
```json
{"id":"firstname-lastname-cmu","tier":"A","name":"","institution":"","departments":[""],
 "position":{"value":"","evidence":{"source_url":"","quote":"","checked_on":"YYYY-MM-DD"}},
 "position_class":"assistant","start_year":null,
 "email":{"value":"","evidence":{"source_url":"","quote":"","checked_on":"YYYY-MM-DD"}},
 "homepage":null,"lab_website":null,"google_scholar":null,
 "keywords":[],"keywords_evidence":{"source_url":"","quote":"","checked_on":"YYYY-MM-DD"},
 "recent_papers":[{"title":"","year":2025,"url":"","source":"homepage"}],
 "recruiting":{"status":"Unknown","evidence":null},
 "relevance":"yes","relevance_reason":"","institute":null,"notes":""}
```
