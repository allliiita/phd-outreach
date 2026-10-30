"""The only LLM step before email writing: relevance / keywords / fit, from compact dossiers.

  python -m outreach.judge prep data/dossiers/cmu-stat.jsonl   # -> data/judge/in/cmu-stat_NN.md (25 people each)
  (a cheap subagent runs agents/25_judge.md on each file -> data/judge/out/cmu-stat_NN.jsonl)
  python -m outreach.judge assemble cmu-stat                   # dossier + judgement -> data/people/cmu-stat.jsonl

Cost control: people whose title already rules them out (emeritus, teaching, adjunct...) never reach the
judge; each person is ~250 tokens (title, <=600 chars of research text, <=6 paper titles, recruiting lines).
Anti-invention: assemble() keeps a keyword only if it occurs in the research text or a paper title, takes
papers / email / quotes from the dossier (never from the judge), and drops a recruiting status whose quote
is not one of the dossier's verbatim lines.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

from .config import ROOT, institutions
from .papers import _norm

DATA = ROOT / "data"
DOSS, JIN, JOUT, PEOPLE = DATA / "dossiers", DATA / "judge" / "in", DATA / "judge" / "out", DATA / "people"
BATCH = 25
OLD_ASSOC = 2010   # associate professors whose first paper predates this are not "young" (applicant scope)
SKIP_CLASSES = {"emeritus", "teaching", "staff_scientist"}
A_CLASSES = {"assistant", "incoming_assistant", "associate", "full", "institute_pi", "research_faculty"}


def slug_id(name: str, institution: str) -> str:
    alias = next((i.get("aliases", [i["name"]])[0] for i in institutions()["institutions"] if i["name"] == institution), institution)
    s = re.sub(r"[^a-z0-9]+", "-", f"{name} {alias}".lower())
    return s.strip("-")


def _load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def prep(path: Path) -> None:
    from .surnames import PRIORITY
    rows = [d for d in _load(path) if d["position_class"] not in SKIP_CLASSES | {"full"}
            and not (d["position_class"] == "associate" and (d.get("first_paper") or 9999) < OLD_ASSOC)]
    rows.sort(key=lambda d: PRIORITY[d.get("heritage")])
    JIN.mkdir(parents=True, exist_ok=True)
    for old in JIN.glob(f"{path.stem}_*.md"):
        old.unlink()
    for b in range(0, len(rows), BATCH):
        out = [f"<!-- batch {path.stem}_{b // BATCH:02d}: {len(rows[b:b + BATCH])} people -->"]
        for d in rows[b:b + BATCH]:
            out.append(f"\n## {slug_id(d['name'], d['institution'])}\n{d['name']} | {d['title_on_roster']} | {d['department']}"
                       + (" | FILTER: ML-relevant faculty only" if d.get("filter") == "ml_only" else ""))
            if d["research"]["text"]:
                out.append(f"research: {d['research']['text'][:600]}")
            if d["papers"]:
                out.append("papers: " + " || ".join(f"[{i}] {p['title']} ({p['year']})" for i, p in enumerate(d["papers"][:6])))
            for i, r in enumerate(d["recruiting"][:3]):
                out.append(f"recruit[{i}]: {r['quote'][:250]}")
            for s in d["start"][:2]:
                out.append(f"start: {s['quote'][:160]}")
        f = JIN / f"{path.stem}_{b // BATCH:02d}.md"
        f.write_text("\n".join(out) + "\n")
        print(f"{f}  ~{len(f.read_text()) // 4} tokens")
    print(f"{len(rows)} people to judge ({len(_load(path)) - len(rows)} skipped by title)")


def _in_text(kw: str, hay: str) -> bool:
    k = _norm(kw)
    return bool(k) and k in hay


def assemble(stem: str) -> None:
    from .roster import clean_name
    doss = {slug_id(d["name"], d["institution"]): d for d in _load(DOSS / f"{stem}.jsonl")}
    judged = {}
    for f in sorted(JOUT.glob(f"{stem}_*.jsonl")):
        for j in _load(f):
            judged[j["id"]] = j
    today = date.today().isoformat()
    people, issues = [], []
    for pid, d in doss.items():
        j = judged.get(pid)
        if d["position_class"] not in SKIP_CLASSES and j is None:
            issues.append(f"{pid}\tnot judged yet")
            continue
        j = j or {"relevance": "no", "relevance_reason": f"skipped by title: {d['title_on_roster']}", "keywords": []}
        hay = _norm(d["research"]["text"] + " " + " ".join(p["title"] for p in d["papers"]))
        kws = [k for k in j.get("keywords", []) if _in_text(k, hay)]
        dropped = [k for k in j.get("keywords", []) if k not in kws]
        if dropped:
            issues.append(f"{pid}\tdropped keywords not in source text: {dropped}")
        papers = [d["papers"][i] for i in j.get("papers", []) if isinstance(i, int) and i < len(d["papers"])][:3] or d["papers"][:3]
        cls = j.get("position_class") or d["position_class"]
        rec = {"status": "Unknown", "evidence": None}
        ri = j.get("recruiting_index")
        if j.get("recruiting") in ("Confirmed", "Not recruiting") and isinstance(ri, int) and ri < len(d["recruiting"]):
            r = d["recruiting"][ri]
            if r["years"] and max(r["years"]) < date.today().year:  # rule 11: stale statements are not current
                issues.append(f"{pid}\tstale recruiting statement ignored ({max(r['years'])})")
            else:
                rec = {"status": j["recruiting"], "evidence": {"source_url": r["source_url"], "quote": r["quote"], "checked_on": today}}
        if rec["status"] == "Unknown" and cls in ("assistant", "incoming_assistant"):
            rec["status"] = "Possible"
        start = None
        if j.get("start_year"):
            sq = next((s for s in d["start"] if str(j["start_year"]) in s["quote"]), None)
            if sq:
                start = {"value": str(j["start_year"]), "evidence": {"source_url": sq["source_url"], "quote": sq["quote"], "checked_on": today}}
        rel = j.get("relevance", "no")
        tier = "A" if (rel in ("yes", "borderline") and cls in A_CLASSES and 3 <= len(kws) and papers and d["research"]["text"]) else "B"
        why_b = [] if tier == "A" or rel == "no" or cls not in A_CLASSES else \
            [w for w, bad in (("papers", not papers), ("keywords", len(kws) < 3), ("research text", not d["research"]["text"])) if bad]
        people.append({
            "id": slug_id(clean_name(d["name"]), d["institution"]), "tier": tier, "name": clean_name(d["name"]), "institution": d["institution"], "departments": [d["department"]],
            "position": d["position"], "position_class": cls, "start_year": start, "email": d["email"],
            "homepage": d["homepage"], "lab_website": d["lab_website"], "google_scholar": d["google_scholar"],
            "keywords": kws[:8] if tier == "A" or len(kws) >= 3 else [],
            "keywords_evidence": {"source_url": d["research"]["source_url"], "quote": d["research"]["text"][:300], "checked_on": today}
            if d["research"]["text"] else None,
            "recent_papers": papers if tier == "A" else papers[:3],
            "fit": j.get("fit"), "fit_projects": j.get("fit_projects", []), "heritage": d.get("heritage"),
            "first_paper": d.get("first_paper"), "moved": (j.get("notes") or "").startswith("MOVED"),
            "recruiting": rec, "relevance": rel, "relevance_reason": j.get("relevance_reason", ""), "institute": None,
            "notes": "; ".join(filter(None, [j.get("notes", ""), f"fit {j['fit']}/5 via {','.join(j.get('fit_projects', []))}" if j.get("fit") else "",
                                              f"A-tier blocked by missing {', '.join(why_b)}" if why_b else "", *d["problems"]])),
        })
    PEOPLE.mkdir(parents=True, exist_ok=True)
    (PEOPLE / f"{stem}.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in people))
    for i in issues:
        print(i)
    print(f"{stem}: {len(people)} records, tier A {sum(p['tier'] == 'A' for p in people)}, {len(issues)} issues")


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    prep(Path(arg)) if cmd == "prep" else assemble(arg)
