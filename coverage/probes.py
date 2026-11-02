"""Independent probes: who do outside sources say is a young ML-ish faculty member at an in-scope school?

  python -m coverage.probes [csrankings|nsf_career|nih_early ...]   # -> data/probes/<probe>.jsonl

Rows {name, school, year, source_url, detail}; only schools in scope.schools() (institutes under their via-school)
and names passing scope.heritage_ok. No LLM. <= 3 requests/s, backoff on 429/5xx.
  csrankings  all areas, no AI minimum; young proxy = first CSRankings paper >= 2012 (outreach/csrankings.py logic)
  nsf_career  NSF CAREER awards starting 2018-2026 (api.nsf.gov), PI name; kept when title/abstract mention ML terms
  nih_early   NIH RePORTER R00 / K99 / DP2, FY2020-2026, contact PI; kept when title/terms/abstract mention ML terms
Cached raw downloads: data/seeds/ (gitignored).
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict

import requests

from outreach.config import canonical_institution, institutions

from . import scope
from .scope import DATA

SEEDS = DATA / "seeds"
OUT = DATA / "probes"
BASE = "https://raw.githubusercontent.com/emeryberger/CSrankings/gh-pages/"
YOUNG_SINCE = 2012
NSF_YEARS = range(2018, 2027)
NIH_YEARS = range(2020, 2027)
ML = re.compile(r"machine[- ]learning|deep[- ]learning|neural|artificial intelligence|\bAI\b|\bML\b|learning[- ]based|"
                r"reinforcement learning|language model|generative|foundation model|computer vision|data[- ]driven|"
                r"statistical learning|representation learning|algorithm|inference|large language|transformer|"
                r"computational (model|biology|neuro)|bayesian|optimization|robot", re.I)
_last = [0.0]


def get(method: str, url: str, **kw):
    """Rate-limited (<= 3 req/s) request with exponential backoff on 429 / 5xx / network errors."""
    for attempt in range(8):
        wait = 0.34 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = requests.request(method, url, timeout=120, **kw)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(60, 2 ** attempt * 2))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"giving up on {url}")


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split())


def org_school(org: str) -> str | None:
    """In-scope school for an awardee / organisation string from NSF or NIH, else None."""
    n = _norm(org)
    for pat, school in ORG_PATTERNS:
        if re.search(pat, n):
            return scope.school_of(school)
    return None


# Order matters (specific before generic). Patterns run on the normalised (lowercase, no punctuation) string.
ORG_PATTERNS = [
    (r"\bweill\b.*\bcornell|\bcornell\b", "Cornell University"),
    (r"\bicahn\b|\bmount sinai\b", "Icahn School of Medicine at Mount Sinai"),
    (r"\brockefeller university\b", "Rockefeller University"),
    (r"\bcold spring harbor\b", "Cold Spring Harbor Laboratory"),
    (r"\bsalk institute\b", "Salk Institute"),
    (r"\ballen institute for ai\b|\bai2\b|\ballen institute for artificial", "Allen Institute for AI"),
    (r"\ballen institute\b", "Allen Institute"),
    (r"\barc institute\b", "Arc Institute"),
    (r"\bbiohub\b", "Chan Zuckerberg Biohub"),
    (r"\buniversity of california,? ?san francisco\b|\buc san francisco\b|\bucsf\b", "University of California San Francisco"),
    (r"\buniversity of california ?(san diego|la jolla)\b|\bucsd\b", "University of California San Diego"),
    (r"\buniversity of california ?irvine\b|\buc irvine\b", "University of California Irvine"),
    (r"\buniversity of california ?santa cruz\b|\buc santa cruz\b", "University of California Santa Cruz"),
    (r"\buniversity of california ?santa barbara\b|\buc santa barbara\b", "University of California Santa Barbara"),
    (r"\bjohns hopkins\b", "Johns Hopkins University"),
    (r"\bboston university\b", "Boston University"),
    (r"\bduke university\b|\bduke univ\b", "Duke University"),
    (r"\buniversity of south florida\b|\busf\b", "University of South Florida"),
    (r"\buniversity of central florida\b", "University of Central Florida"),
    (r"\buniversity of washington\b", "University of Washington"),
    (r"\buniversity of maryland(?! baltimore| eastern| global)", "University of Maryland"),
    (r"\bgeorgia (institute of technology|tech)\b", "Georgia Institute of Technology"),
    (r"\buniversity of michigan\b|\bregents of the university of michigan\b", "University of Michigan"),
    (r"^(the |trustees of the )?university of pennsylvania\b", "University of Pennsylvania"),
    (r"\buniversity of massachusetts amherst\b|\bumass amherst\b|\buniv of massachusetts amherst\b", "University of Massachusetts Amherst"),
    (r"\bnew york university\b|\bnyu\b", "New York University"),
]
NOT_ORG = re.compile(r"university of washington (state|tacoma)|washington university|university of michigan (dearborn|flint)|"
                     r"university of pennsylvania state|penn state|georgia state|georgia southern", re.I)


def write(name: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seen, out = set(), []
    for r in rows:
        k = (r["school"], scope.name_key(r["name"]), r["year"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    (OUT / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    people = {(r["school"], scope.name_key(r["name"])) for r in out}
    print(f"{name}: {len(out)} hits, {len(people)} distinct people, {len({r['school'] for r in out})} schools", flush=True)


def seed(name: str):
    f = SEEDS / name
    if not f.exists():
        SEEDS.mkdir(parents=True, exist_ok=True)
        f.write_bytes(get("GET", BASE + name).content)
    return csv.DictReader(f.open(encoding="utf-8"))


def csrankings() -> None:
    aff: dict[str, str] = {}   # CSRankings affiliation string -> in-scope school
    for i in institutions()["institutions"]:
        s = scope.school_of(i["name"])
        if s:
            aff[i.get("csrankings", i["name"])] = s
    for r in seed("csrankings.csv"):   # affiliations without a `csrankings` field in institutions.yaml (UCSC): normalise
        a = r["affiliation"]
        if a not in aff:
            s = scope.school_of(a.replace("Univ. of", "University of").replace(" - ", " "))
            if s:
                aff[a] = s
    first: dict[str, int] = {}
    papers: dict[tuple, Counter] = defaultdict(Counter)
    for r in seed("generated-author-info.csv"):
        y = int(r["year"])
        first[r["name"]] = min(first.get(r["name"], 9999), y)
        if r["dept"] in aff and y >= 2021:
            papers[(r["name"], r["dept"])][r["area"]] += float(r["count"])
    rows = []
    for r in seed("csrankings.csv"):
        school = aff.get(r["affiliation"])
        nm = re.sub(r"\s+\d{4}$", "", r["name"])
        if not school or first.get(r["name"], 0) < YOUNG_SINCE or not scope.heritage_ok(nm):
            continue
        c = papers.get((r["name"], r["affiliation"]), Counter())
        rows.append({"name": nm, "school": school, "year": first[r["name"]], "source_url": r["homepage"] or "https://csrankings.org/",
                     "detail": {"first_paper": first[r["name"]], "papers_since_2021": round(sum(c.values()), 1),
                                "areas": dict(c.most_common(4)), "affiliation": r["affiliation"]}})
    write("csrankings", rows)


def _pi_name(first: str, last: str) -> str:
    return f"{first} {last}".strip()


NSF_NAMES = ["Cornell University", "Trustees of Boston University", "Duke University", "University of South Florida",
             "University of California-San Francisco", "Cold Spring Harbor Laboratory", "Icahn School of Medicine at Mount Sinai",
             "Johns Hopkins University", "The University of Central Florida Board of Trustees", "Rockefeller University",
             "University of Washington", "University of California-San Diego", "University of Maryland, College Park",
             "Georgia Tech Research Corporation", "Georgia Institute of Technology", "University of California-Irvine",
             "University of California-Santa Cruz", "Regents of the University of Michigan - Ann Arbor",
             "University of Pennsylvania", "University of Massachusetts Amherst", "University of California-Santa Barbara",
             "New York University", "Salk Institute for Biological Studies", "Allen Institute", "Chan Zuckerberg Biohub"]


def nsf_career() -> None:
    """Per awardee (quoted = exact phrase; unquoted NSF search is any-word); fundProgramName=CAREER alone misses most
    awards, so also keyword=CAREER with title starting \"CAREER\"."""
    url = "https://api.nsf.gov/services/v1/awards.json"
    fields = "id,awardeeName,startDate,fundProgramName,title,piFirstName,piLastName,abstractText"
    rows, orgs, total = [], Counter(), 0
    seen_id: set[str] = set()
    for org, sel in [(o, k) for o in NSF_NAMES for k in ({"fundProgramName": "CAREER"}, {"keyword": "CAREER"})]:
        off, n = 1, 0
        while True:
            p = {"awardeeName": f'"{org}"', **sel, "startDateStart": f"01/01/{NSF_YEARS[0]}",
                 "startDateEnd": f"12/31/{NSF_YEARS[-1]}", "rpp": 25, "offset": off, "printFields": fields}
            aw = get("GET", url, params=p).json().get("response", {}).get("award", [])
            for a in aw:
                n += 1
                if a["id"] in seen_id or not (a.get("title") or "").upper().startswith("CAREER"):
                    continue
                seen_id.add(a["id"])
                if NOT_ORG.search(a.get("awardeeName") or ""):
                    continue
                school = org_school(a.get("awardeeName") or "")
                if not school:
                    continue
                orgs[a["awardeeName"]] += 1
                nm = _pi_name(a.get("piFirstName") or "", a.get("piLastName") or "")
                if not nm or not scope.heritage_ok(nm):
                    continue
                if not ML.search(f"{a.get('title') or ''} {a.get('abstractText') or ''}"):
                    continue
                rows.append({"name": nm, "school": school, "year": int(a["startDate"][-4:]),
                             "source_url": f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={a['id']}",
                             "detail": {"title": a.get("title"), "awardee": a["awardeeName"], "start": a["startDate"]}})
            if len(aw) < 25:
                break
            off += 25
        total += n
    print(f"  nsf: {total} CAREER awards read, {sum(orgs.values())} at in-scope schools:", dict(orgs.most_common(40)))
    write("nsf_career", rows)


def nih_early() -> None:
    url = "https://api.reporter.nih.gov/v2/projects/search"
    rows, orgs, total = [], Counter(), 0
    for y in NIH_YEARS:
        for code in ("R00", "K99", "DP2"):
            off = 0
            while True:
                b = {"criteria": {"activity_codes": [code], "fiscal_years": [y]}, "offset": off, "limit": 500,
                     "include_fields": ["ProjectTitle", "ContactPiName", "PrincipalInvestigators", "Organization", "FiscalYear",
                                        "ActivityCode", "ProjectNum", "ProjectDetailUrl", "Terms", "AbstractText"]}
                d = get("POST", url, json=b).json()
                res = d.get("results") or []
                for r in res:
                    total += 1
                    org = (r.get("organization") or {}).get("org_name") or ""
                    school = org_school(org) if not NOT_ORG.search(org) else None
                    if not school:
                        continue
                    orgs[org] += 1
                    pis = r.get("principal_investigators") or []
                    pi = next((p for p in pis if p.get("is_contact_pi")), pis[0] if pis else None)
                    nm = _pi_name(pi.get("first_name") or "", pi.get("last_name") or "") if pi else ""
                    if not nm or not scope.heritage_ok(nm):
                        continue
                    text = f"{r.get('project_title') or ''} {r.get('terms') or ''} {r.get('abstract_text') or ''}"
                    if not ML.search(text):
                        continue
                    rows.append({"name": nm.title() if nm.isupper() else nm, "school": school, "year": y,
                                 "source_url": r.get("project_detail_url") or f"https://reporter.nih.gov/project-details/{r.get('appl_id')}",
                                 "detail": {"title": r.get("project_title"), "activity": code, "project_num": r.get("project_num"),
                                            "org": org}})
                off += 500
                if off >= (d.get("meta") or {}).get("total", 0) or off >= 14500 or not res:
                    break
        print(f"  nih FY{y}: {total} projects read so far", flush=True)
    print("  nih orgs matched:", dict(orgs.most_common(40)))
    write("nih_early", rows)


PROBES = {"csrankings": csrankings, "nsf_career": nsf_career, "nih_early": nih_early}


def main() -> None:
    for name in sys.argv[1:] or list(PROBES):
        PROBES[name]()


if __name__ == "__main__":
    main()
