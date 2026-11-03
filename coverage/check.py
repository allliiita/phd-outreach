"""The done predicate (CLAUDE.md), per school. Exit 0 = done; exit 1 while anything is open. Never relaxed.

  python -m coverage.check [--school NAME]

Columns: big units open | recall misses | funnel open | listed unverified.
  units     every census row (data/grid/<slug>.units.jsonl) with decision covered/added maps via grid_unit to a grid row
            (data/grid/<slug>.jsonl) with status done (rows == page_count) or alt; no census or no grid file = open
  recall    probe hit (data/probes/*.jsonl) whose (school, name_key) is neither in the people ledger nor in
            data/coverage/explained.jsonl {school, name, reason}
  funnel    in-scope ledger people whose outcome is still "open"
  unverified listed people whose verify record is not backed by saved snapshots (page exists, ML quote and email on it)
  waiting on human  open units / recall misses / funnel people named in data/coverage/human_requests.jsonl
            {school, unit, url, why[, name]}: listed in their own column, not counted as open work, but still non-terminal
            (exit 1 while any exist). A request with `unit` covers that unit's open problems; with `name` it covers that person.
Run `python -m coverage.ledger` and `python -m coverage.probes` first; the check only reads their files.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict

from . import scope
from .scope import DATA, SLUG, jl

PROBES = ("csrankings", "nsf_career", "nih_early")
TERMINAL = ("done", "alt")


def units(school: str) -> list[str]:
    """Reasons this school's BIG units are not terminal; empty list = all done."""
    slug = SLUG.get(school)
    if not slug:
        return ["no grid slug in coverage.scope.SLUG"]
    census = jl(DATA / "grid" / f"{slug}.units.jsonl")
    grid = jl(DATA / "grid" / f"{slug}.jsonl")
    if not census:
        return ["no census (data/grid/%s.units.jsonl)" % slug]
    if not grid:
        return ["no grid (data/grid/%s.jsonl)" % slug]
    by_unit = defaultdict(list)
    for g in grid:
        by_unit[g.get("unit")].append(g)
    bad, seen = [], set()
    for c in census:
        if c.get("decision") not in ("covered", "added"):
            continue
        gu = c.get("grid_unit")
        parts = [gu] if gu in by_unit else split_units(gu) or [gu]   # "A; B" = two units
        for gu in parts:
            if gu not in seen:
                seen.add(gu)
                bad += _unit_problems(gu, by_unit.get(gu), c)
    return bad


def split_units(gu: str | None) -> list[str]:
    """'A; B' -> two grid units. A ';' inside parentheses belongs to the name: 'Robotics (field; members in CS/ECE)' is ONE unit
    (2026-11-02: it was split into 'Robotics (field' + 'members in CS/ECE)' and could never match a grid row)."""
    return [x.strip() for x in re.split(r";(?![^()]*\))", gu or "") if x.strip()]


def _unit_problems(gu, rows, c) -> list[str]:
    if not gu or not rows:
        return [f"{gu or c.get('unit')}: census says {c['decision']} but no grid row"]
    bad = []
    for g in rows:
        st = g.get("status")
        if st not in TERMINAL:
            bad.append(f"{gu}: {st}" + (f" ({(g.get('note') or '')[:70]})" if g.get("note") else ""))
        elif st == "done" and g.get("page_count") is not None and g.get("rows") != g.get("page_count"):
            bad.append(f"{gu}: done but roster rows {g.get('rows')} != page count {g.get('page_count')}")
    return bad


def human_requests() -> list[dict]:
    return [h for h in jl(DATA / "coverage" / "human_requests.jsonl") if h.get("school")]


def _waits_unit(school: str, problem: str, reqs: list[dict]) -> bool:
    return any(h["school"] == school and h.get("unit") and not h.get("name") and problem.startswith(h["unit"] + ":") for h in reqs)


def _waits_person(school: str, name: str, reqs: list[dict]) -> bool:
    k = scope.name_key(name)
    return any(h["school"] == school and h.get("name") and scope.name_key(h["name"]) == k for h in reqs)


def explained() -> set[tuple]:
    return {(e["school"], scope.name_key(e["name"])) for e in jl(DATA / "coverage" / "explained.jsonl")
            if e.get("school") and e.get("name") and e.get("reason")}


def _truncated(school: str, key: tuple, name: str, known: set) -> bool:
    """NSF award PI names are cut at 29 characters ('Cristian Danescu-Niculescu-Mi'): match the cut surname as a prefix."""
    if len(name) < 28 or len(key) != 2:
        return False
    a, b = key
    return any(s == school and len(k) == 2 and any(x == a and y != b and y.startswith(b) or x == b and y != a and y.startswith(a)
                                                   for x, y in (k, k[::-1])) for s, k in known)


def recall(ledger: list[dict]) -> dict[tuple, dict]:
    """(school, name_key) -> {name, probes: {probe: year}} for probe hits found nowhere."""
    known = {(r["school"], tuple(r["key"])) for r in ledger} | explained()
    miss: dict[tuple, dict] = {}
    for p in PROBES:
        for h in jl(DATA / "probes" / f"{p}.jsonl"):
            k = (h["school"], scope.name_key(h["name"]))
            if k not in known and not _truncated(h["school"], k[1], h["name"], {x for x in known}):
                m = miss.setdefault(k, {"school": h["school"], "name": h["name"], "probes": {}, "url": h.get("source_url")})
                m["probes"][p] = h.get("year")
    return miss


def unverified(ledger: list[dict]) -> list[dict]:
    """Listed people whose verify record can't be re-checked on saved snapshots (fail closed: no snapshot = unverified)."""
    from outreach.fetch import emails
    from outreach.verify import page, quote_ok
    recs = {}
    people = {p["id"]: p for p in jl(DATA / "tag" / "people.jsonl") if p.get("id")}
    for v in jl(DATA / "verify" / "result.jsonl"):
        p = people.get(v["id"]) or v
        recs[(scope.school_of(p.get("institution") or "") or p.get("institution"), scope.name_key(p.get("name") or ""))] = v
    bad = []
    for r in ledger:
        if not r.get("in_scope") or r.get("outcome") != "listed":
            continue
        v = recs.get((r["school"], tuple(r["key"])))
        why = None
        if not v:
            why = "no verify record"
        elif not page(v.get("official_page") or ""):
            why = f"no saved snapshot of {v.get('official_page')}"
        elif (e := quote_ok(v["official_page"], v.get("ml_quote") or "")):
            why = e
        elif (v.get("email") or "").lower() not in {a.lower() for a, _ in emails(page(v["official_page"])[0])}:
            why = f"email {v.get('email')} not on {v['official_page']}"
        if why:
            bad.append({"school": r["school"], "name": r["name"], "why": why})
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school")
    a = ap.parse_args(argv)
    ledger = jl(DATA / "coverage" / "people.jsonl")
    missing = recall(ledger)
    unver = unverified(ledger)
    want = [s for s in scope.schools() if not a.school or a.school.lower() in s.lower()]
    reqs = human_requests()
    print(f"{'school':44} {'big units open':>14} {'recall misses':>13} {'funnel open':>11} {'listed unverified':>17} {'waiting on human':>16}")
    total = 0
    detail = {}
    for s in want:
        u_all = units(s)
        rm_all = [m for m in missing.values() if m["school"] == s]
        fo_all = [r for r in ledger if r["school"] == s and r.get("in_scope") and str(r.get("outcome")).startswith("open")]
        wait = ([("unit", x) for x in u_all if _waits_unit(s, x, reqs)]
                + [("recall", m["name"]) for m in rm_all if _waits_person(s, m["name"], reqs)]
                + [("funnel", r["name"]) for r in fo_all if _waits_person(s, r["name"], reqs)])
        u = [x for x in u_all if not _waits_unit(s, x, reqs)]
        rm = [m for m in rm_all if not _waits_person(s, m["name"], reqs)]
        fo = [r for r in fo_all if not _waits_person(s, r["name"], reqs)]
        lu = [x for x in unver if x["school"] == s]
        detail[s] = (u, rm, fo, lu, wait)
        total += len(u) + len(rm) + len(fo) + len(lu) + len(wait)
        print(f"{s[:44]:44} {len(u):>14} {len(rm):>13} {len(fo):>11} {len(lu):>17} {len(wait):>16}")
    print(f"{'TOTAL':44} {sum(len(d[0]) for d in detail.values()):>14} {sum(len(d[1]) for d in detail.values()):>13} "
          f"{sum(len(d[2]) for d in detail.values()):>11} {sum(len(d[3]) for d in detail.values()):>17} {sum(len(d[4]) for d in detail.values()):>16}")
    if a.school:
        for s, (u, rm, fo, lu, wait) in detail.items():
            print(f"\n== {s}\n-- big units open ({len(u)})")
            for x in u:
                print("  ", x)
            print(f"-- recall misses ({len(rm)}): add the person to a roster/unit or explain in data/coverage/explained.jsonl")
            for m in sorted(rm, key=lambda m: m["name"]):
                print(f"   {m['name']}  {m['probes']}  {m['url']}")
            print(f"-- funnel open ({len(fo)})")
            for r in fo:
                tag = "" if r["outcome"] == "open" else "[" + r["outcome"].split(" ")[0] + "] "
                print(f"   {tag}{r['name']} | {r['title'][:40]} | {', '.join(r['units'])[:60]}")
            print(f"-- waiting on human ({len(wait)}): see data/coverage/human_requests.jsonl; still not done")
            for kind, x in wait:
                print(f"   [{kind}] {x[:110]}")
            print(f"-- listed unverified ({len(lu)})")
            for x in lu:
                print(f"   {x['name']}: {x['why'][:110]}")
    if not (DATA / "snapshots").exists():
        print("\nnote: data/snapshots/ is missing on this machine, so every listed row counts as unverified")
    print("\nDONE" if total == 0 else f"\nNOT DONE: {total} open items")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
