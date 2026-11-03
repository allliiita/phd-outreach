"""Write or update ONE unit row of data/grid/<slug>.jsonl so counts are computed, never typed.

  python -m coverage.gridrow --school "Cornell University" --unit "Computer Science" --status alt \
      --roster data/roster/cornell-bowers-directory.jsonl --page-count 240 \
      --alt-source https://bowers.cornell.edu/directory --note "why / evidence" [--url U ...] [--group G1] [--rename NEW]

  rows        = lines in --roster (the script counts them)
  page_count  = --page-count N: faculty entries counted on the page by coverage.pagecount / a human count (evidence in --note)
  status done = roster rows == page_count (coverage.check enforces); alt = covered by another source (needs --alt-source)
  no roster   = status blocked/todo/none with a note
The row is matched by exact unit name (or --match OLD when renaming); other rows are kept as they are.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .scope import DATA, SLUG, jl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True)
    ap.add_argument("--unit", required=True)
    ap.add_argument("--status", required=True, choices=["done", "alt", "blocked", "todo", "found", "none"])
    ap.add_argument("--roster", type=Path)
    ap.add_argument("--page-count", type=int)
    ap.add_argument("--alt-source")
    ap.add_argument("--note", default="")
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--group", default=None)
    ap.add_argument("--match", help="existing unit name to replace (when the unit is being renamed)")
    a = ap.parse_args(argv)
    if a.status == "alt" and not a.alt_source:
        ap.error("status alt needs --alt-source (URL)")
    if a.status == "done":
        if not a.roster or a.page_count is None:
            ap.error("status done needs --roster and --page-count (rows must equal the faculty count on the page)")
        n = sum(1 for l in a.roster.read_text().splitlines() if l.strip())
        if n != a.page_count:
            print(f"refused: roster has {n} rows but page_count is {a.page_count} (diff {n - a.page_count:+d}). "
                  f"Run `python -m coverage.pagecount --yaml <yaml> --roster {a.roster}` to see dropped / missing names; "
                  f"staff in the roster or a real professor dropped by skip_titles is the usual cause. Use --status found/blocked until they match.",
                  file=sys.stderr)
            return 2
    path = DATA / "grid" / f"{SLUG[a.school]}.jsonl"
    rows = jl(path)
    old = next((r for r in rows if r.get("unit") == (a.match or a.unit)), None)
    new = dict(old or {"institution": a.school, "group": a.group or "G1", "urls": [], "titles": None})
    new.update(unit=a.unit, status=a.status, note=a.note)
    if a.group:
        new["group"] = a.group
    if a.url:
        new["urls"] = a.url
    if a.roster:
        new["roster"] = str(a.roster)
        new["rows"] = sum(1 for l in a.roster.read_text().splitlines() if l.strip())
        new["page_count"] = a.page_count if a.page_count is not None else new.get("page_count")
    else:
        new.setdefault("roster", None)
        new.setdefault("rows", None)
        new.setdefault("page_count", a.page_count)
    if a.alt_source:
        new["alt_source"] = a.alt_source
    rows = [new if r is old else r for r in rows] if old else rows + [new]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{a.unit}: {a.status} rows={new.get('rows')} page_count={new.get('page_count')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
