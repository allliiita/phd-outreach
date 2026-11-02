"""Industry-side view: where do researchers at top AI labs come from? (applicant's end goal, 2026-11-02)

  python -m outreach.labsource scan      # stream the dblp dump once -> data/labs/persons.jsonl (lab affiliation + homepage)
  python -m outreach.labsource phd       # fetch homepages, extract PhD school / advisor / years by regex -> data/labs/phd.jsonl
  python -m outreach.labsource report    # tallies -> data/labs/summary.json

dblp person records (<www key="homepages/...">) carry an affiliation note maintained by dblp and homepage URLs. The
dblp API and OpenReview are bot-checked for us; the dump is dblp's own bulk download. PhD facts are taken only
from the person's own homepage text (quote saved), never guessed.
"""
from __future__ import annotations

import gzip
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from xml.etree.ElementTree import iterparse

from .config import ROOT
from .dblp import DUMP, _Entities

OUT = ROOT / "data" / "labs"
LABS = {   # applicant 2026-11-02: OpenAI and Anthropic excluded
    "Google DeepMind": r"deepmind",
    "Google Research": r"google (?:research|brain)|\bgoogle\b(?!.*deepmind)",
    "Meta FAIR": r"\bmeta\b|facebook ai|\bfair\b",
    "Microsoft Research": r"microsoft research|\bmsr\b",
    "NVIDIA Research": r"nvidia",
    "Apple MLR": r"\bapple\b",
    "Amazon": r"amazon|\baws\b",
    "Allen Institute (Ai2)": r"allen institute for (?:ai|artificial intelligence)|\bai2\b",
    "Flatiron Institute": r"flatiron",
    "Isomorphic Labs": r"isomorphic",
    "Genentech / Prescient Design": r"genentech|prescient design",
    "Chan Zuckerberg (CZI / Biohub)": r"chan zuckerberg|czi\b|biohub",
    "Toyota Research Institute": r"toyota research",
    "IBM Research": r"\bibm\b",
}
LAB_RE = {k: re.compile(v, re.I) for k, v in LABS.items()}
SKIP_URL = re.compile(r"scholar\.google|orcid\.org|wikidata|dblp\.org|linkedin|twitter|x\.com|researchgate|semanticscholar|"
                      r"mathgenealogy|genealogy\.math|github\.com/[^/]+/?$|zbmath|viaf|isni|d-nb\.info", re.I)


def scan() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    curl = subprocess.Popen(["curl", "-sL", DUMP], stdout=subprocess.PIPE)
    n, kept = 0, []
    for _, el in iterparse(_Entities(gzip.GzipFile(fileobj=curl.stdout)), events=("end",)):
        if el.tag in ("article", "inproceedings", "incollection", "proceedings", "book", "phdthesis", "mastersthesis", "www"):
            if el.tag == "www" and (el.get("key") or "").startswith("homepages/"):
                aff = [x.text or "" for x in el.findall("note") if x.get("type") == "affiliation"]
                labs = [k for k, r in LAB_RE.items() if any(r.search(a) for a in aff)]
                if labs:
                    urls = [u.text for u in el.findall("url") if u.text and not SKIP_URL.search(u.text)]
                    kept.append({"name": (el.findtext("author") or ""), "key": el.get("key"), "labs": labs,
                                 "affiliations": aff, "urls": urls})
            el.clear()
            n += 1
            if n % 2_000_000 == 0:
                print(f"{n:,} records, {len(kept)} lab persons", flush=True)
    curl.wait()
    (OUT / "persons.jsonl").write_text("".join(json.dumps(p) + "\n" for p in kept))
    print(f"{len(kept)} persons with a lab affiliation; with homepage: {sum(bool(p['urls']) for p in kept)}")


PHD = re.compile(r"[^.\n]{0,160}\b(?:Ph\.?\s?D\.?|PhD|doctorate|doctoral (?:degree|studies))\b[^.\n]{0,220}", re.I)
SCHOOL = re.compile(r"((?:University of [A-Z][\w&\-]+(?: [A-Z][\w&\-]+){0,3}(?:,? [A-Z][\w]+)?)|(?:[A-Z][\w&\-.]+(?: [A-Z][\w&\-.]+){0,4} "
                    r"(?:University|Institute of Technology|Institute|College|Polytechnic|ETH Zurich|EPFL))|MIT|CMU|UC Berkeley|"
                    r"Berkeley|Stanford|Caltech|EPFL|ETH Zurich|UCLA|UCSD|UIUC|Mila|Oxford|Cambridge|Toronto|Princeton|Harvard|"
                    r"Columbia|Cornell|NYU|Johns Hopkins|Georgia Tech|UW|Tsinghua|Peking University|KAIST)")
ADVISOR = re.compile(r"(?:advised by|advisor(?:s)?(?: was| were| is)?:?|supervised by|under the (?:supervision|guidance) of|"
                     r"working with)\s+(?:Prof(?:essor)?\.?\s+|Dr\.?\s+)?([A-Z][\w'’.\-]+(?: [A-Z][\w'’.\-]+){1,3})")
YEAR = re.compile(r"\b(20[0-2]\d|19[89]\d)\b")


def phd() -> None:
    from .fetch import get, visible_text
    persons = [json.loads(l) for l in (OUT / "persons.jsonl").read_text().splitlines() if l.strip()]
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    by_lab = defaultdict(list)
    for p in persons:
        if p["urls"]:
            by_lab[p["labs"][0]].append(p)
    todo = [p for lab, ps in by_lab.items() for p in ps[:cap]]

    def one(p):
        for u in p["urls"][:2]:
            try:
                t = visible_text(get(u))
            except Exception:  # noqa: BLE001
                continue
            hits = [m.group(0).strip() for m in PHD.finditer(t)]
            for h in hits:
                sm = SCHOOL.search(h)
                if sm:
                    am = ADVISOR.search(h) or ADVISOR.search(t[t.find(h): t.find(h) + 600])
                    yrs = YEAR.findall(h)
                    return {**p, "phd_school": sm.group(1), "phd_quote": h[:300], "advisor": am.group(1) if am else "",
                            "years_in_quote": yrs, "source_url": u}
        return {**p, "phd_school": None}

    with ThreadPoolExecutor(12) as ex:
        res = list(ex.map(one, todo))
    (OUT / "phd.jsonl").write_text("".join(json.dumps(r) + "\n" for r in res))
    print(f"{len(res)} homepages tried, PhD school found for {sum(bool(r['phd_school']) for r in res)}")


def report() -> None:
    rs = [json.loads(l) for l in (OUT / "phd.jsonl").read_text().splitlines() if l.strip()]
    norm = {"MIT": "Massachusetts Institute of Technology", "CMU": "Carnegie Mellon University", "Berkeley": "UC Berkeley",
            "University of California, Berkeley": "UC Berkeley", "Stanford": "Stanford University", "UW": "University of Washington"}
    summ = {"overall": Counter(), "by_lab": defaultdict(Counter), "advisors": Counter(), "n": len(rs),
            "found": sum(bool(r["phd_school"]) for r in rs)}
    for r in rs:
        if not r["phd_school"]:
            continue
        s = norm.get(r["phd_school"], r["phd_school"])
        summ["overall"][s] += 1
        for lab in r["labs"]:
            summ["by_lab"][lab][s] += 1
        if r.get("advisor"):
            summ["advisors"][f'{r["advisor"]} ({s})'] += 1
    out = {"n": summ["n"], "found": summ["found"], "overall": summ["overall"].most_common(60),
           "by_lab": {k: v.most_common(15) for k, v in summ["by_lab"].items()}, "advisors": summ["advisors"].most_common(60)}
    (OUT / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["overall"][:25]))


if __name__ == "__main__":
    {"scan": scan, "phd": phd, "report": report}[sys.argv[1]]()
