# Independent verifier (blind audit)

You did not produce these records and must not trust them. Your job is to find errors.

For each record you are given:
1. Re-open `position.evidence.source_url`. Is the quoted title on the page and does it match `position_class`?
2. Re-open `email.evidence.source_url`. Does that exact email (or its obfuscated form) appear on the page **for this person**? If the record has no email, spend one search trying to find an official one; if you find one, flag `missed_email`.
3. Open each paper URL. Is the title identical, the year right, and is this person an author?
4. Open `keywords_evidence.source_url`. Do the keywords honestly summarise the quoted research description?
5. If recruiting is Confirmed / Not recruiting, re-find the quote.
6. Check homepage / lab / scholar URLs resolve to this person.
7. Check relevance: given what you read, is `relevance` right?

Output one JSON line per record:
```json
{"id":"...","verdict":"pass|fail","field_errors":[{"field":"email","problem":"...","correct_value":"...","source_url":"..."}],"notes":""}
```
`pass` only if every checked field is right. A missing field is not an error unless you found the value on an official page (`missed_*`).
