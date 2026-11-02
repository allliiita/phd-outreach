"""Alternate roster for a CS unit whose official faculty page cannot be read: CSRankings faculty of the school.

  python -m coverage.csr_unit --school "Cornell University"     # -> data/roster/<slug>-csrankings.jsonl

One row per CSRankings faculty member at the school (data/probes/csrankings.jsonl, built by coverage.probes), no title
(coverage.titles fills it from the homepage). Use it NEXT TO a partial source (e.g. a college directory), never instead
of reading the official page when that page is reachable.
"""
from __future__ import annotations

import argparse
import json

from .scope import DATA, SLUG, jl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True)
    a = ap.parse_args(argv)
    rows, seen = [], set()
    for h in jl(DATA / "probes" / "csrankings.jsonl"):
        if h["school"] != a.school or h["name"] in seen:
            continue
        seen.add(h["name"])
        rows.append({"name": h["name"], "institution": a.school, "department": "Computer Science (CSRankings)",
                     "title_on_roster": "", "roster_url": "https://csrankings.org/", "profile_url": h.get("source_url"),
                     "quote": f"{h['name']} {a.school} CSRankings first paper {h.get('year')}", "filter": "all"})
    out = DATA / "roster" / f"{SLUG[a.school]}-csrankings.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{len(rows)} CSRankings faculty -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
