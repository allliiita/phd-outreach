"""Can this professor pay a PhD student? Active federal awards from public APIs (no key needed).

  python -m outreach.funding        # people in data/tag/people.jsonl with fit A/B -> data/funding.jsonl

NSF award search (api.nsf.gov) and NIH RePORTER (api.reporter.nih.gov). A person is matched only when the award's PI
name equals theirs AND the awardee organisation matches their institution (same-name PIs elsewhere are dropped).
"""
from __future__ import annotations

import glob
import json
import re
import time

import requests

from .config import ROOT
from .validate import norm_name

DATA = ROOT / "data"
INST_WORDS = {"Boston University": "boston univ", "Duke University": "duke", "University of South Florida": "south florida",
              "University of California San Francisco": "san francisco", "Cold Spring Harbor Laboratory": "cold spring",
              "Icahn School of Medicine at Mount Sinai": "mount sinai", "Johns Hopkins University": "johns hopkins",
              "University of Central Florida": "central florida", "Cornell University": "cornell",
              "Rockefeller University": "rockefeller", "University of Washington": "university of washington",
              "University of California San Diego": "san diego", "University of Maryland": "maryland",
              "Georgia Institute of Technology": "georgia tech", "University of California Irvine": "irvine",
              "University of California Santa Cruz": "santa cruz"}


def nsf(name: str, inst: str) -> list[dict]:
    r = requests.get("https://api.nsf.gov/services/v1/awards.json", timeout=40, params={
        "pdPIName": name, "printFields": "id,title,startDate,expDate,awardeeName,fundsObligatedAmt,piFirstName,piLastName"})
    awards = (r.json().get("response") or {}).get("award") or []
    w = INST_WORDS.get(inst, inst.lower())
    out = []
    for a in awards:
        if w in (a.get("awardeeName") or "").lower() and norm_name(f'{a.get("piFirstName", "")} {a.get("piLastName", "")}') == norm_name(name):
            out.append({"src": "NSF", "id": a["id"], "title": a.get("title"), "start": a.get("startDate"), "end": a.get("expDate"),
                        "amount": a.get("fundsObligatedAmt"), "career": "CAREER" in (a.get("title") or "")})
    return out


def nih(name: str, inst: str) -> list[dict]:
    r = requests.post("https://api.reporter.nih.gov/v2/projects/search", timeout=40, json={
        "criteria": {"pi_names": [{"any_name": name}], "fiscal_years": [2024, 2025, 2026]}, "limit": 50,
        "include_fields": ["ProjectNum", "ProjectTitle", "Organization", "AwardAmount", "ProjectStartDate", "ProjectEndDate",
                           "PrincipalInvestigators"]})
    w = INST_WORDS.get(inst, inst.lower())
    out = []
    for p in r.json().get("results") or []:
        org = ((p.get("organization") or {}).get("org_name") or "").lower()
        pis = [norm_name(x.get("full_name", "")) for x in p.get("principal_investigators") or []]
        if w.split()[0] in org and norm_name(name) in pis:
            out.append({"src": "NIH", "id": p.get("project_num"), "title": p.get("project_title"), "start": p.get("project_start_date"),
                        "end": p.get("project_end_date"), "amount": p.get("award_amount"), "career": False})
    return out


def main() -> None:
    tags = {}
    for f in sorted(glob.glob(str(DATA / "tag" / "out" / "*.jsonl"))) + sorted(glob.glob(str(DATA / "tag" / "re_out" / "*.jsonl"))):
        for l in open(f):
            t = json.loads(l)
            tags[t["id"]] = t
    for f in glob.glob(str(DATA / "dossier_out" / "*.jsonl")):
        for l in open(f):
            d = json.loads(l)
            if d.get("fit"):
                tags.setdefault(d["id"], {})["fit"] = d["fit"]
    people = [json.loads(l) for l in (DATA / "tag" / "people.jsonl").read_text().splitlines() if l.strip()]
    todo = [p for p in people if tags.get(p["id"], {}).get("fit") in ("A", "B")]
    out = []
    for p in todo:
        aw = []
        for fn in (nsf, nih):
            try:
                aw += fn(p["name"], p["institution"])
            except Exception as e:  # noqa: BLE001
                aw.append({"src": fn.__name__, "error": str(e)[:80]})
            time.sleep(0.4)
        yr = lambda d: int((re.search(r"(19|20)\d\d", str(d or "")) or [0])[0] or 0)
        active = [a for a in aw if not a.get("error") and yr(a.get("end")) >= 2026]
        out.append({"id": p["id"], "name": p["name"], "awards": aw, "active_awards": len(active),
                    "active_amount": sum(int(float(a.get("amount") or 0)) for a in active),
                    "nsf_career": any(a.get("career") for a in aw)})
    (DATA / "funding.jsonl").write_text("".join(json.dumps(o) + "\n" for o in out))
    print(f"{len(out)} A/B people; with active federal awards: {sum(o['active_awards'] > 0 for o in out)}; "
          f"NSF CAREER: {sum(o['nsf_career'] for o in out)}")


if __name__ == "__main__":
    main()
