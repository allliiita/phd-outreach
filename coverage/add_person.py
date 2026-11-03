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
import re

from .titles import title_near_name as find_title
from outreach.fetch import get, visible_text

from .scope import DATA, SLUG, bare_name, jl


def full_title(vis: str, name: str, title: str, institution: str = "") -> str:
    """`title` (as find_title returned it, capped at ~60 chars of 'of X') extended to the end of its clause: up to the institution
    name, a sentence end or a line break. Never cut mid-word."""
    if not title:
        return title
    parts = bare_name(name).split()
    i = vis.find(title)
    if parts:
        for m in re.finditer(re.escape(parts[0]), vis):
            j = vis.find(title, m.start())
            if 0 <= j - m.start() <= 400:
                i = j
                break
    if i < 0:
        return title
    clause = vis[i: i + 300]
    from outreach.config import canonical_institution, institutions
    c = canonical_institution(institution)
    names = [c] + [a for inst in institutions()["institutions"] if inst["name"] == c for a in inst.get("aliases", []) + [inst.get("csrankings", "")]]
    cuts = [m.start() for n in names if n for m in [re.search(re.escape(n), clause)] if m and m.start() > len(title) // 2]
    cuts += [m.start() for m in re.finditer(r"[.;|\n(]|\s{3,}", clause) if m.start() >= len(title)]
    out = clause[: min(cuts)] if cuts else clause[:200].rsplit(" ", 1)[0]
    out = re.sub(r"(?:,|\s+at|\s+-|\s+\u2013)+\s*$", "", out.strip()).strip(" ,")
    return out if out.lower().startswith(title.lower()[:10]) and len(out) >= len(title) else title


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--unit", default="probe miss added from official profile")
    a = ap.parse_args(argv)
    vis = visible_text(get(a.url))
    title = full_title(vis, a.name, find_title(vis, a.name), a.school)
    out = DATA / "roster" / f"{SLUG[a.school]}-probe-adds.jsonl"
    rows = [r for r in jl(out) if r["name"] != a.name]
    rows.append({"name": a.name, "institution": a.school, "department": a.unit, "title_on_roster": title, "roster_url": a.url,
                 "profile_url": a.url, "quote": vis[:300], "filter": "all"})
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{a.name}: title {title!r} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
