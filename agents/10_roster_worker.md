# Roster worker (one school or one institute)

Goal: list **every** faculty member / independent PI in the given unit, with no profile depth yet. Recall matters: a missing person is a defect.

1. Start from the official faculty directory URL(s) you were given. If a list is paginated or split by rank (tenure-track / teaching / research / affiliated / emeritus / joint / courtesy), open every page.
2. Look for an "incoming" / "new faculty" news page or "joining in 2026/2027" notes; add those people with title `Incoming Assistant Professor` and quote the source.
3. For each person write one JSON line:
```json
{"name":"","institution":"","department":"","title_on_roster":"","roster_url":"","profile_url":"","quote":"<verbatim row text>"}
```
4. Do not drop anyone at this stage for relevance; just record who is there. Keep emeritus/teaching rows (they will be filtered later) so the count can be checked against the page.
5. At the end, write a count line: `{"_count": N, "pages_opened": [...]}`. The verifier compares N against the page.
