"""Why does a roster have fewer rows than the page has entries? Lists every person block on the page and what dropped it.

  python -m coverage.pagecount URL [--yaml config/directories/x.yaml] [--roster data/roster/x.jsonl] [--refresh]

Reads the page with outreach.roster.auto (or the YAML's selectors) with the faculty filter OFF, then reports
  entries   person blocks on the page (deduplicated by name)
  faculty   entries that outreach.roster.faculty_like keeps  (= what the roster should hold; use as grid page_count)
  dropped   the rest, with the title/quote that dropped them (staff, students, postdocs)  <- read this list
  missing   faculty entries that are not in --roster (a parser / pagination bug if non-empty)
Record the numbers and one example in the grid row's note; never edit the roster by hand.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from outreach import roster


def entries(url: str | None, yaml_path: Path | None, refresh: bool) -> list[dict]:
    keep = roster.faculty_like
    roster.faculty_like = lambda r: True          # auto() filters inside; show everything
    try:
        if yaml_path:
            cfg = yaml_path
            import yaml
            c = yaml.safe_load(cfg.read_text())
            c.pop("skip_titles", None)
            c.pop("expect", None)
            tmp = Path("/tmp/_pagecount.yaml")
            tmp.write_text(yaml.safe_dump(c))
            rows, _ = roster.run(tmp, refresh)
        else:
            rows, _ = roster.auto(url, "x", "x", refresh)
    finally:
        roster.faculty_like = keep
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--yaml", type=Path)
    ap.add_argument("--roster", type=Path)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    rows = entries(a.url, a.yaml, a.refresh)
    skip = []
    if a.yaml:   # the YAML's own skip_titles decide what the roster drops; this list is what you review
        import yaml
        skip = [re.compile(x, re.I) for x in yaml.safe_load(a.yaml.read_text()).get("skip_titles", [])]

    def is_fac(r):
        t = r["title_on_roster"]
        return not any(p.search(t) for p in skip) if a.yaml else roster.faculty_like(r)
    fac = [r for r in rows if is_fac(r)]
    drop = [r for r in rows if not is_fac(r)]
    print(f"entries {len(rows)}  faculty {len(fac)}  dropped {len(drop)}")
    for r in drop:
        print(f"  dropped: {r['name']} | {r['title_on_roster'][:60]} | {r['quote'][:80]}")
    if a.roster:
        have = {json.loads(l)["name"].lower() for l in a.roster.read_text().splitlines() if l.strip()}
        miss = [r["name"] for r in fac if r["name"].lower() not in have]
        print(f"missing from roster ({len(miss)}): {miss[:20]}")


if __name__ == "__main__":
    main()
