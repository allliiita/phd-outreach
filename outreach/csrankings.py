"""CS faculty seed from CSRankings (curated by hand, has homepage + Scholar id): no directory scraping
and no LLM for CS departments.

  python -m outreach.csrankings [--min 2 --since 2021]     # -> data/roster/csr-<alias>.jsonl per institution

Pre-filter (free): keep people with >= --min papers since --since at ML / vision / NLP / AI / comp-bio
venues (CSRankings' own venue lists). Robotics, systems, theory etc. are left out.
Young only (applicant preference): first paper anywhere in CSRankings >= --young-since. Calibrated on CMU:
every assistant professor's first paper is >= 2012, almost every full professor's is <= 2011.
Output is ordered by outreach.surnames priority (Chinese, other East Asian, South Asian, rest), then AI output.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict

import requests

from .config import ROOT, institutions
from .surnames import PRIORITY, asian_tag

SEEDS = ROOT / "data" / "seeds"
BASE = "https://raw.githubusercontent.com/emeryberger/CSrankings/gh-pages/"
AREAS = {"nips", "icml", "iclr", "aaai", "ijcai", "cvpr", "iccv", "eccv", "acl", "emnlp", "naacl", "kdd", "ismb", "recomb"}


def _seed(name: str):
    f = SEEDS / name
    if not f.exists():
        SEEDS.mkdir(parents=True, exist_ok=True)
        f.write_bytes(requests.get(BASE + name, timeout=300).content)
    return csv.DictReader(f.open(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=2)
    ap.add_argument("--since", type=int, default=2021)
    ap.add_argument("--young-since", type=int, default=2012)
    a = ap.parse_args()
    want = {}
    for i in institutions()["institutions"]:
        if i.get("kind") != "institute":
            want[i.get("csrankings", i["name"])] = i
    counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    first: dict[str, int] = {}
    for r in _seed("generated-author-info.csv"):
        first[r["name"]] = min(first.get(r["name"], 9999), int(r["year"]))
        if r["dept"] in want and r["area"] in AREAS and int(r["year"]) >= a.since:
            counts[(r["name"], r["dept"])][r["area"]] += float(r["count"])
    out = defaultdict(list)
    for r in _seed("csrankings.csv"):
        c = counts.get((r["name"], r["affiliation"]))
        if not c or sum(c.values()) < a.min or first.get(r["name"], 0) < a.young_since:
            continue
        inst = want[r["affiliation"]]
        sid = r["scholarid"] if r["scholarid"] not in ("", "NOSCHOLARPAGE") else None
        out[inst['name']].append({
            "name": re.sub(r"\s+\d{4}$", "", r["name"]), "institution": inst["name"], "department": "Computer Science (CSRankings)",
            "title_on_roster": "", "roster_url": "https://csrankings.org/", "profile_url": r["homepage"], "homepage": r["homepage"],
            "google_scholar": f"https://scholar.google.com/citations?user={sid}" if sid else None,
            "quote": f"{r['name']},{r['affiliation']},{r['homepage']}",
            "ai_venues": dict(c.most_common(4)), "ai_papers": round(sum(c.values()), 1), "filter": "all",
            "first_paper": first[r["name"]], "heritage": asian_tag(r["name"]),
        })
    dest = ROOT / "data" / "roster"
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    byname = {i["name"]: i for i in want.values()}
    for name, rows in out.items():
        inst = byname[name]
        alias = re.sub(r"[^a-z0-9]+", "-", inst.get("aliases", [inst["name"]])[0].lower()).strip("-")
        rows.sort(key=lambda x: (PRIORITY[x["heritage"]], -x["ai_papers"]))
        (dest / f"csr-{alias}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
        total += len(rows)
    print(f"{total} young CS faculty (first paper >= {a.young_since}) with >= {a.min} ML/AI/vision/NLP/bio papers since {a.since}"
          f" at {len(out)} institutions; heritage {dict(Counter(x['heritage'] for v in out.values() for x in v))}")
    for name, rows in sorted(out.items(), key=lambda x: -len(x[1]))[:8]:
        print(f"  {name}: {len(rows)}")


if __name__ == "__main__":
    main()
