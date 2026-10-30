"""Deterministic checks on drafted emails (layer 2 for the email stage).

  python -m outreach.emailcheck data/drafts.jsonl data/people.jsonl
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .config import profile
from .schema import Person

BANNED = [
    "hope this email finds you", "deeply passionate", "groundbreaking", "esteemed", "renowned",
    "i have read all", "your impressive work", "your inspiring work", "delve", "recommendation letter",
    "letter of recommendation", "recommender", "my publication", "my paper", "i published",
    "tapestry", "i am writing to express my", "cutting-edge",
]


def check_one(d: dict, p: Person) -> list[str]:
    errs = []
    body, subj = d["body"], d["subject"]
    low = (subj + "\n" + body).lower()
    words = len(body.split())
    if not 110 <= words <= 230:
        errs.append(f"length {words} words (want 130-200)")
    for b in BANNED:
        if b in low:
            errs.append(f"banned phrase: {b!r}")
    if p.email is None:
        errs.append("record has no verified email")
    elif d["to"].lower() != p.email.value.lower():
        errs.append(f"to={d['to']} differs from verified email {p.email.value}")
    last = p.name.split()[-1]
    first_line = body.strip().splitlines()[0]
    if last.lower() not in first_line.lower():
        errs.append(f"salutation does not use surname {last!r}: {first_line!r}")
    if "professor" in first_line.lower() and "professor" not in p.position.value.lower():
        errs.append("addressed as Professor but title is not a professorship")
    # every quoted/mentioned paper must be one of the record's papers
    known = [x.title.lower() for x in p.recent_papers]
    for q in re.findall(r"[\"“]([^\"”]{12,})[\"”]", body):
        if not any(q.lower().strip(" .,") in k or k in q.lower() for k in known):
            errs.append(f"quoted title not in record: {q[:60]!r}")
    if not any(k[:40] in low for k in known) and "notes" not in json.dumps(d.get("claims", [])):
        errs.append("email does not reference any specific paper or sourced note")
    for c in d.get("claims", []):
        if c.get("field") not in {"recent_papers", "notes", "keywords", "recruiting", "institute", "position"}:
            errs.append(f"claim from unknown field: {c}")
    app = profile()
    if not app.get("mention_recommenders", False) and "recommend" in low:
        errs.append("mentions recommendation")
    if "fall 2027" not in low:
        errs.append("does not state target term Fall 2027")
    for other in re.findall(r"Professor\s+([A-Z][a-z]+)", body):
        if other.lower() != last.lower() and other.lower() not in body.splitlines()[0].lower():
            errs.append(f"mentions another professor: {other}")
    return errs


def main() -> None:
    drafts = [json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
    people = {}
    for f in sys.argv[2:]:
        for l in Path(f).read_text().splitlines():
            if l.strip() and not l.startswith('{"_'):
                p = Person.model_validate_json(l)
                people[p.id] = p
    bad = 0
    for d in drafts:
        errs = check_one(d, people[d["id"]]) if d["id"] in people else ["no such person record"]
        for e in errs:
            print(f"{d['id']}\t{e}")
        bad += bool(errs)
    print(f"# {len(drafts)} drafts, {bad} failing", file=sys.stderr)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
