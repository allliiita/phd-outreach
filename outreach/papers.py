"""Recent papers from OpenAlex (structured, so titles/years are never typed by an LLM).

  python -m outreach.papers "Firstname Lastname" "Carnegie Mellon University" [--homepage URL]

Author disambiguation: candidate OpenAlex authors are scored by institution match; ambiguous cases
print all candidates and exit 2 so an agent (or human) picks, rather than silently choosing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import requests

API = "https://api.openalex.org"
MAILTO = {"mailto": "lm3879@columbia.edu"}


def candidates(name: str, institution: str) -> list[dict]:
    r = requests.get(f"{API}/authors", params={"search": name, "per-page": 15, **MAILTO}, timeout=30)
    r.raise_for_status()
    out = []
    inst_tokens = {t for t in institution.lower().replace(",", " ").split() if len(t) > 3}
    for a in r.json()["results"]:
        insts = [i.get("display_name", "") for i in (a.get("last_known_institutions") or [])]
        insts += [x["institution"]["display_name"] for x in a.get("affiliations", [])[:5]]
        score = max((len(inst_tokens & set(i.lower().split())) for i in insts), default=0)
        out.append({"id": a["id"], "name": a["display_name"], "works": a.get("works_count", 0),
                    "institutions": insts[:4], "score": score})
    return sorted(out, key=lambda c: (-c["score"], -c["works"]))


def recent_works(author_id: str, n: int = 3) -> list[dict]:
    since = date.today().year - 3
    r = requests.get(f"{API}/works", params={
        "filter": f"author.id:{author_id.split('/')[-1]},from_publication_date:{since}-01-01,type:article|preprint|proceedings-article",
        "sort": "cited_by_count:desc", "per-page": 25, **MAILTO}, timeout=30)
    r.raise_for_status()
    picked, seen = [], set()
    for w in r.json()["results"]:
        t = (w.get("title") or "").strip()
        if not t or t.lower() in seen:
            continue
        seen.add(t.lower())
        url = w.get("doi") or (w.get("primary_location") or {}).get("landing_page_url") or w["id"]
        picked.append({"title": t, "year": w["publication_year"], "url": url, "source": "openalex"})
        if len(picked) == n:
            break
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("institution")
    ap.add_argument("--author-id")
    a = ap.parse_args()
    if a.author_id:
        print(json.dumps(recent_works(a.author_id), indent=1))
        return
    c = candidates(a.name, a.institution)
    good = [x for x in c if x["score"] > 0]
    if len(good) == 1 or (len(good) > 1 and good[0]["score"] > good[1]["score"]):
        print(json.dumps({"author": good[0], "papers": recent_works(good[0]["id"])}, indent=1))
    else:
        print(json.dumps({"ambiguous": c[:6]}, indent=1))
        sys.exit(2)


if __name__ == "__main__":
    main()
