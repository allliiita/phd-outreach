# Department discovery (stage 0, one institution)

Goal: the list of official directory URLs to roster for one institution. A missed department means a missed group of professors, so this stage is verified too.

1. For each kind in `config/institutions.yaml: target_departments`, find the unit at this institution (search "<institution> <unit> faculty directory"). Units can be named differently (e.g. "Machine Learning Department", "Biomedical Data Science", "Quantitative Biomedical Sciences", "Data Science Institute").
2. For each unit, record the official faculty directory URL(s), split by rank pages if the site splits them.
3. For units where only some faculty are relevant (ECE, OR, Applied Math, Neuroscience), set `"filter": "ml_only"`.
4. For institutes, record the PI directory page(s) and the official page that explains how its PIs take PhD students.

Output lines to `data/departments.jsonl`:
```json
{"institution":"","unit":"","url":"","filter":"all|ml_only","quote":"<page heading verbatim>"}
```
The verifier re-opens each URL, confirms it is the official directory of that unit, and searches once more for any target unit that is missing.
