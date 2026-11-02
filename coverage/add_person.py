"""Put a probe hit that no roster lists into the people ledger, from an official page that shows them.

  python -m coverage.add_person --school "Cornell University" --name "Yicheng Long" --url https://gradschool.weill.cornell.edu/person/yicheng-long --unit "Weill graduate faculty"

Fetches --url (saved snapshot), reads the title with outreach.enrich.find_title, appends one roster row to
data/roster/<slug>-probe-adds.jsonl (the title may be empty; coverage.titles fills it later). Then rerun coverage.ledger.
Use this when the person IS in scope-by-title (assistant/associate) but was missed by the unit rosters; use
data/coverage/explained.jsonl when the person is legitimately out of scope.
"""
from __future__ import annotations

import argparse
import json

from .titles import title_near_name as find_title
from outreach.fetch import get, visible_text

from .scope import DATA, SLUG, jl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--unit", default="probe miss added from official profile")
    a = ap.parse_args(argv)
    vis = visible_text(get(a.url))
    title = find_title(vis, a.name)
    out = DATA / "roster" / f"{SLUG[a.school]}-probe-adds.jsonl"
    rows = [r for r in jl(out) if r["name"] != a.name]
    rows.append({"name": a.name, "institution": a.school, "department": a.unit, "title_on_roster": title, "roster_url": a.url,
                 "profile_url": a.url, "quote": vis[:300], "filter": "all"})
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{a.name}: title {title!r} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
