"""People ledger: one row per (school, person) from every top-level roster, one outcome per in-scope person.

  python -m coverage.ledger        # -> data/coverage/people.jsonl

Rows from rosters of out-of-scope schools are skipped. Institutes count under their via-school (scope.via()).
A person is in scope if ANY of their roster rows passes scope.gate(); the gate failures of the rest are kept.
Outcome (in scope only), from existing results, first match wins:
  data/verify/result.jsonl   pass + email -> listed | pass w/o email -> rejected:no email | fail -> rejected:<why>
  data/tag/out/*.jsonl       fit C -> rejected:not ML      (joined to data/tag/people.jsonl by id)
  otherwise                  open
Out of scope people keep a row (so a probe hit on them is "found") with outcome out_of_scope:<gate>.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter

from outreach.roster import faculty_like
from outreach.surnames import asian_tag

from . import scope
from .scope import DATA, jl

SKIP = ("csr-", "ps-", "scout-test")


def roster_files() -> list:
    return [p for p in sorted((DATA / "roster").glob("*.jsonl"))
            if not p.name.startswith(SKIP) and p.name != "x.jsonl"]


def _old_keep(r: dict) -> bool:
    """The pre-coverage rule (batch1.keep) on the raw name, to measure what credential-aware names add."""
    from outreach.enrich import young_title
    t = r.get("title_on_roster") or ""
    return faculty_like(r) and (not t or young_title(t)) and asian_tag(r.get("name") or "") == "chinese"


def results() -> dict[tuple[str, tuple], dict]:
    """(school, name_key) -> {verify: row|None, fit: str|None} from the existing pipeline outputs."""
    out: dict[tuple, dict] = {}
    people = {p["id"]: p for p in jl(DATA / "tag" / "people.jsonl") if p.get("id")}

    def key(p):
        return (scope.school_of(p.get("institution") or "") or p.get("institution"), scope.name_key(p.get("name") or ""))
    for v in jl(DATA / "verify" / "result.jsonl"):
        p = people.get(v["id"]) or v
        out.setdefault(key(p), {})["verify"] = v
    for f in sorted(glob.glob(str(DATA / "tag" / "out" / "*.jsonl"))):
        for t in jl(f):
            p = people.get(t.get("id"))
            if p:
                out.setdefault(key(p), {})["fit"] = t.get("fit")
    return out


def outcome(res: dict | None) -> str:
    res = res or {}
    v = res.get("verify")
    if v:
        if v.get("pass"):
            return "listed" if v.get("email") else "rejected:no email"
        return "rejected:" + "; ".join(v.get("why") or ["failed verification"])[:160]
    if res.get("fit") == "C":
        return "rejected:not ML"
    return "open"


def build() -> list[dict]:
    people: dict[tuple, dict] = {}
    for f in roster_files():
        for r in jl(f):
            if not r.get("name"):
                continue
            school = scope.school_of(r.get("institution") or "")
            if not school:
                continue
            k = scope.name_key(r["name"])
            if k == ("", ""):
                continue
            p = people.setdefault((school, k), {"school": school, "name": r["name"], "key": list(k), "rows": []})
            p["rows"].append({"unit": r.get("department"), "file": f.name, "title": r.get("title_on_roster") or "",
                              "url": r.get("profile_url") or r.get("roster_url"), "gate": scope.gate(r),
                              "old_keep": _old_keep(r), "institution": r.get("institution"),
                              "email": r.get("block_email") or None})
    res = results()
    out = []
    for (school, k), p in sorted(people.items(), key=lambda x: (x[0][0], x[0][1])):
        ok = [r for r in p["rows"] if r["gate"] is None]
        first = (ok or p["rows"])[0]
        in_scope = bool(ok)
        gates = sorted({r["gate"] for r in p["rows"] if r["gate"]})
        row = {"school": school, "name": scope.bare_name(p["name"]), "key": p["key"], "in_scope": in_scope,
               "title": first["title"], "units": sorted({r["unit"] or r["file"] for r in p["rows"]}),
               "sources": sorted({r["file"] for r in p["rows"]}), "profile_url": first["url"],
               "gates": {"faculty": "not faculty" not in gates or bool(ok), "young": "not young" not in gates or bool(ok),
                         "heritage": scope.heritage_ok(p["name"])},
               "old_keep": any(r["old_keep"] for r in p["rows"]),
               "rows_new": sum(1 for r in ok if not r["old_keep"]),
               "block_email": next((r["email"] for r in p["rows"] if r["email"]), None)}
        if in_scope:
            rr = res.get((school, tuple(k)), {})
            row["fit"] = rr.get("fit")
            row["outcome"] = outcome(rr)
        else:
            row["outcome"] = "out_of_scope:" + ("/".join(gates) or "?")
        out.append(row)
    return out


def load() -> list[dict]:
    return jl(DATA / "coverage" / "people.jsonl")


def main() -> None:
    rows = build()
    d = DATA / "coverage"
    d.mkdir(parents=True, exist_ok=True)
    (d / "people.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    ins = [r for r in rows if r["in_scope"]]
    new = [r for r in ins if not r["old_keep"]]
    print(f"{len(rows)} people from rosters, {len(ins)} in scope; {len(new)} in scope that the old keep() rule missed "
          f"({sum(r['rows_new'] for r in ins)} roster rows; credential-suffix names); outcomes {dict(Counter(r['outcome'].split(':')[0] for r in ins))}")
    byschool = Counter(r["school"] for r in new)
    print("  old-rule misses by school:", dict(byschool), file=sys.stdout)


if __name__ == "__main__":
    main()
