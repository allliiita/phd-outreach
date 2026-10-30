# Department discovery (web search only; no page reading beyond what is needed)

Input: a list of institutions. For each, find the official faculty directory URL for these units (skip a unit
the school does not have; skip CS, it is already covered):
- Statistics / Statistics & Data Science
- Biostatistics
- Computational Biology / Bioinformatics / Biomedical Informatics / Biomedical Data Science
- Data Science (only if it appoints its own faculty)
- Computational neuroscience / Brain & Cognitive Sciences  (set "filter": "ml_only")
- Electrical & Computer Engineering                         (set "filter": "ml_only")

Use one web search per unit ("<institution> <unit> faculty directory"). Prefer the page that lists all regular
faculty (not a single research area, not "people" landing pages that only link elsewhere). If faculty are split
by rank on several pages, give each page as its own line.

Append one JSON line per URL to the output file you are given:
{"institution":"<exact name from config/institutions.yaml>","unit":"<unit name as the school writes it>","url":"...","filter":"all|ml_only"}

Do not verify the pages yourself: code scrapes each URL and reports failures. Reply with one line:
`<file>: N urls for M institutions`.
