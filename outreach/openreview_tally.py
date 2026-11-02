"""Tally docs/openreview_lab_history.jsonl (public OpenReview profiles of ICLR'25 / NeurIPS'24 / ICML'25 authors whose
current position is at a top lab; collected by the applicant on her own computer).

  python -m outreach.openreview_tally     # -> data/labs/openreview_summary.json + printed tables
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from .config import ROOT
from .validate import norm_name

SRC = ROOT / "docs" / "openreview_lab_history.jsonl"
OUT = ROOT / "data" / "labs" / "openreview_summary.json"
LABS = [("Google DeepMind", r"deepmind"), ("Google (Research)", r"google"), ("Meta (FAIR/GenAI)", r"\bmeta\b|facebook|fb\.com"),
        ("Microsoft Research", r"microsoft"), ("NVIDIA", r"nvidia"), ("Apple", r"apple"), ("Amazon", r"amazon"),
        ("Ai2", r"allen institute|allenai|\bai2\b"), ("Flatiron", r"flatiron|simons"), ("Isomorphic", r"isomorphic"),
        ("Genentech / Prescient", r"genentech|prescient|gene\.com|roche"), ("CZI / Biohub", r"chan zuckerberg|czi|biohub"),
        ("Toyota Research", r"toyota"), ("IBM Research", r"\bibm\b")]
LAB_RE = [(k, re.compile(v, re.I)) for k, v in LABS]
STUDENT = re.compile(r"intern|student|phd|resident|visiting", re.I)
PHD = re.compile(r"ph\.?\s?d|doctoral", re.I)
ALIAS = {"Massachusetts Institute of Technology": "MIT", "Carnegie Mellon University": "CMU", "Stanford University": "Stanford",
         "University of California, Berkeley": "UC Berkeley", "University of California Berkeley": "UC Berkeley"}


def lab_of(h):
    t = f'{(h.get("institution") or {}).get("name", "")} {(h.get("institution") or {}).get("domain", "")}'
    for k, r in LAB_RE:
        if r.search(t):
            return k
    return None


CANON = [(r"massachusetts institute of technology|\bmit\b", "MIT"), (r"carnegie mellon|\bcmu\b", "CMU"),
         (r"stanford", "Stanford"), (r"berkeley", "UC Berkeley"), (r"urbana|uiuc", "UIUC"),
         (r"university of washington|washington, seattle", "U Washington"), (r"georgia inst|georgia tech", "Georgia Tech"),
         (r"southern california|\busc\b", "USC"), (r"texas,? (?:at )?austin|utexas", "UT Austin"), (r"san diego|ucsd", "UCSD"),
         (r"los angeles|ucla", "UCLA"), (r"johns hopkins", "Johns Hopkins"), (r"maryland", "U Maryland"),
         (r"cornell", "Cornell"), (r"princeton", "Princeton"), (r"new york university|\bnyu\b", "NYU"),
         (r"columbia", "Columbia"), (r"oxford", "Oxford"), (r"cambridge(?!.*mass)", "Cambridge"),
         (r"eth|swiss federal", "ETH Zurich"), (r"epfl|lausanne", "EPFL"), (r"toronto", "Toronto"),
         (r"university college london|\bucl\b", "UCL"), (r"montreal|mila", "Montreal/Mila"), (r"mcgill", "McGill"),
         (r"harvard", "Harvard"), (r"michigan", "U Michigan"), (r"pennsylvania|upenn", "UPenn"),
         (r"duke", "Duke"), (r"boston university", "Boston University"), (r"central florida", "UCF"),
         (r"rutgers", "Rutgers"), (r"stony brook", "Stony Brook"), (r"new jersey institute|njit", "NJIT"),
         (r"northeastern", "Northeastern"), (r"massachusetts,? amherst|umass", "UMass Amherst"), (r"rockefeller", "Rockefeller"),
         (r"san francisco|ucsf", "UCSF"), (r"mount sinai|icahn", "Mount Sinai"), (r"south florida", "USF")]


def school(h):
    n = (h.get("institution") or {}).get("name", "") or (h.get("institution") or {}).get("domain", "")
    for pat, c in CANON:
        if re.search(pat, n, re.I):
            return c
    return ALIAS.get(n, n)


def main() -> None:
    rows = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    hires, interns = [], []
    for p in rows:
        hist = p.get("history") or []
        cur = [(h, lab_of(h)) for h in hist if not h.get("end")]
        cur = [(h, l) for h, l in cur if l]
        if not cur:
            continue
        phds = [h for h in hist if PHD.search(h.get("position") or "")]
        advisors = [r.get("name") or r.get("username", "") for r in p.get("relations") or []
                    if re.search(r"phd advisor|advisor|supervisor", r.get("relation", ""), re.I)]
        h0, lab = cur[0]
        rec = {"name": p.get("name"), "lab": lab, "position": h0.get("position"), "start": h0.get("start"),
               "phd_school": school(phds[0]) if phds else None, "phd_end": phds[0].get("end") if phds else None,
               "phd_ongoing": bool(phds and not phds[0].get("end")), "advisors": advisors}
        (interns if STUDENT.search(h0.get("position") or "") or rec["phd_ongoing"] else hires).append(rec)
    recent = [r for r in hires if r["phd_school"] and (r["phd_end"] or 0) >= 2020]
    out = {"profiles": len(rows), "hires": len(hires), "interns_or_students": len(interns), "recent_phd_hires": len(recent),
           "recent_hire_phd_schools": Counter(r["phd_school"] for r in recent).most_common(60),
           "recent_by_lab": {lab: Counter(r["phd_school"] for r in recent if r["lab"] == lab).most_common(12)
                             for lab in dict.fromkeys(r["lab"] for r in recent)},
           "intern_current_schools": Counter(r["phd_school"] for r in interns if r["phd_school"]).most_common(60),
           "advisors_of_recent_hires": Counter(f'{a} ({r["phd_school"]})' for r in recent for a in r["advisors"]).most_common(80),
           "advisors_of_interns": Counter(f'{a} ({r["phd_school"]})' for r in interns for a in r["advisors"] if r["phd_school"]).most_common(80)}
    # cross-check with our list: which of our professors appear as advisors of lab hires / interns
    ours = {}
    for f in (ROOT / "data" / "tag").glob("people.jsonl"):
        for l in f.read_text().splitlines():
            q = json.loads(l)
            ours[norm_name(q["name"])] = q["institution"]
    hits, homonyms = defaultdict(list), defaultdict(list)
    for r in hires + interns:
        for a in r["advisors"]:
            if norm_name(a) in ours:
                inst = ours[norm_name(a)]
                same = r["phd_school"] and school({"institution": {"name": inst}}) == r["phd_school"]
                (hits if same else homonyms)[f'{a} ({inst})'].append(
                    f'{r["name"]} [PhD {r["phd_school"]}] -> {r["lab"]} ({"intern/student" if r in interns else "hire"})')
    out["our_professors_as_advisors"] = dict(hits)            # PhD school == professor's current school
    out["name_matches_other_school"] = dict(homonyms)          # likely a same-name professor elsewhere, or a past job
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print({k: out[k] for k in ("profiles", "hires", "interns_or_students", "recent_phd_hires")})
    print("RECENT HIRES' PhD schools:", out["recent_hire_phd_schools"][:30])
    print("INTERNS' current schools:", out["intern_current_schools"][:30])
    print("OUR PROFESSORS AS ADVISORS:", json.dumps(out["our_professors_as_advisors"], indent=0)[:1500])


if __name__ == "__main__":
    main()
