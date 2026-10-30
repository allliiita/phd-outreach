"""Find PIs from papers instead of directories (for schools whose websites block us).

  python -m outreach.papersource "University of California San Francisco" [--heritage chinese] [--max 2000]
  -> data/roster/ps-<alias>.jsonl (roster rows) + email evidence snapshots

Europe PMC (PubMed + bioRxiv/medRxiv), last 3 years, AI / computational / omics papers with an author
affiliated with the school. A PI = last author with that affiliation. Emails come only from the paper's own
affiliation text ("Electronic address: x@ucsf.edu"), saved as a snapshot so validate.py can re-check them.
"Young" is estimated from the year of the person's first paper at this institution as last author.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date

from .config import ROOT, institution_domains, institutions
from .fetch import SNAP, snapshot_path
from .papers import EPMC, _aff_terms, _get
from .surnames import asian_tag

TOPIC = ('(TITLE_ABS:"machine learning" OR TITLE_ABS:"deep learning" OR TITLE_ABS:"artificial intelligence" '
         'OR TITLE_ABS:"foundation model" OR TITLE_ABS:"language model" OR TITLE_ABS:"computational" '
         'OR TITLE_ABS:"single-cell" OR TITLE_ABS:"spatial transcriptomics" OR TITLE_ABS:"neural network" '
         'OR TITLE_ABS:"statistical method" OR TITLE_ABS:"bioinformatic" OR TITLE_ABS:"imaging")')


def _aff(a: dict) -> str:
    return " ".join(i.get("affiliation", "") for i in (a.get("authorAffiliationDetailsList") or {}).get("authorAffiliation", []))


def run(institution: str, heritage: str | None, cap: int) -> list[dict]:
    terms = _aff_terms(institution)
    low = [t.lower() for t in terms]
    doms = institution_domains(institution)
    aff_q = " OR ".join(f'AFF:"{t}"' for t in terms)
    since = date.today().year - 3
    people: dict[str, dict] = defaultdict(lambda: {"papers": [], "emails": {}, "affs": []})
    cursor, seen = "*", 0
    while seen < cap:
        r = _get(EPMC, {"query": f"({aff_q}) AND {TOPIC} AND PUB_YEAR:[{since} TO {date.today().year}]",
                        "format": "json", "pageSize": 1000, "resultType": "core", "cursorMark": cursor}, gap=0.3)
        res = r.get("resultList", {}).get("result", [])
        if not res:
            break
        for x in res:
            al = (x.get("authorList") or {}).get("author", [])
            if not al or len(al) > 40:
                continue
            last = al[-1]
            aff = _aff(last)
            if not any(t in aff.lower() for t in low) or not last.get("firstName") or not last.get("lastName"):
                continue
            name = f"{last['firstName']} {last['lastName']}"
            if heritage and asian_tag(name) != heritage:
                continue
            p = people[name]
            url = f"https://europepmc.org/article/{x.get('source')}/{x.get('id')}"
            p["papers"].append({"title": x.get("title", "").rstrip("."), "year": int(x.get("pubYear") or 0), "url":
                                f"https://doi.org/{x['doi']}" if x.get("doi") else url, "source": "europepmc"})
            p["affs"].append(aff)
            for m in re.finditer(r"[\w.+-]+@[\w.-]+\.\w+", aff):
                em = m.group(0).rstrip(".").lower()
                dom = em.split("@")[1]
                if any(dom == d or dom.endswith("." + d) for d in doms):
                    p["emails"][em] = (url, aff)
        seen += len(res)
        nxt = r.get("nextCursorMark")
        if not nxt or nxt == cursor:
            break
        cursor = nxt
    rows = []
    for name, p in people.items():
        if len(p["papers"]) < 2:      # one paper as last author is too thin to call someone a PI
            continue
        first_tok = name.split()[0].lower()[:3]
        last_tok = name.split()[-1].lower()
        mine = {e: v for e, v in p["emails"].items() if last_tok in e or first_tok in e.split("@")[0]}
        row = {"name": name, "institution": institution, "department": "(from papers)",
               "title_on_roster": "", "roster_url": "https://europepmc.org/", "profile_url": None,
               "quote": p["affs"][0][:300], "filter": "all", "heritage": asian_tag(name),
               "ps_papers": sorted(p["papers"], key=lambda w: -w["year"])[:8], "ps_n": len(p["papers"])}
        if mine:
            em, (url, aff) = next(iter(mine.items()))
            sp = snapshot_path(SNAP, url)
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(aff)
            sp.with_suffix(".url").write_text(url)
            row.update(block_email=em, block_email_quote=aff[:600], roster_url=url)
        rows.append(row)
    rows.sort(key=lambda r: -r["ps_n"])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("institution")
    ap.add_argument("--heritage")
    ap.add_argument("--max", type=int, default=3000)
    a = ap.parse_args()
    rows = run(a.institution, a.heritage, a.max)
    inst = next((i for i in institutions()["institutions"] if i["name"] == a.institution), {"name": a.institution})
    alias = re.sub(r"[^a-z0-9]+", "-", (inst.get("aliases") or [inst["name"]])[0].lower()).strip("-")
    out = ROOT / "data" / "roster" / f"ps-{alias}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{out}: {len(rows)} PIs (>=2 last-author papers), {sum('block_email' in r for r in rows)} with email from papers")


if __name__ == "__main__":
    main()
