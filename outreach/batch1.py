"""Batch 1 glue: grid rosters -> enrich (young + Chinese surname only) -> tagger cards -> batch1.xlsx.

  python -m outreach.batch1 rosters          # roster files of the focus schools, from data/grid/*.jsonl
  python -m outreach.batch1 enrich           # enrich.py --heritage chinese on each (young titles only)
  python -m outreach.batch1 cards [--size 40]  # data/tag/in/bNN.jsonl for agents/26_fit_tagger.md
  python -m outreach.batch1 export           # data/export/batch1.xlsx (+ csv)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from .config import ROOT
from .enrich import position_class, young_title
from .roster import faculty_like
from .surnames import asian_tag

DATA = ROOT / "data"
TAG = DATA / "tag"
SLUG = {"Boston University": "boston-university", "Duke University": "duke", "University of South Florida": "usf",
        "University of California San Francisco": "ucsf", "Cold Spring Harbor Laboratory": "cshl",
        "Icahn School of Medicine at Mount Sinai": "mount-sinai", "Washington University in St. Louis": "washu",
        "University of Virginia": "uva", "University of Michigan": "umich", "University of Pennsylvania": "upenn"}


def targets() -> dict:
    return yaml.safe_load((ROOT / "config" / "targets.yaml").read_text())


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def grid() -> list[dict]:
    out = []
    for inst in targets()["focus_schools"]:
        out += [{**g, "institution": g.get("institution") or inst} for g in jl(DATA / "grid" / f"{SLUG[inst]}.jsonl")]
    return out


def rosters() -> list[Path]:
    seen, out = set(), []
    for g in grid():
        r = g.get("roster")
        if g.get("status") == "done" and r and r not in seen and (ROOT / r).exists():
            seen.add(r)
            out.append(ROOT / r)
    return out


def keep(r: dict) -> bool:
    """Young, PhD-advising title (or no title yet) and a Chinese surname. Everything else is out of batch 1."""
    t = r.get("title_on_roster") or ""
    return faculty_like(r) and (not t or young_title(t)) and asian_tag(r["name"]) == "chinese"


def cmd_enrich() -> None:
    for p in rosters():
        n = sum(keep(r) for r in jl(p) if not str(r.get("name", "")).startswith("_"))
        print(f"{p.name}: {n} young Chinese-surname rows", flush=True)
        if n:
            subprocess.run([sys.executable, "-m", "outreach.enrich", str(p), "--heritage", "chinese"],
                           cwd=ROOT, check=False)


def people() -> list[dict]:
    """One record per person (name + institution); departments merged. Dossier rows with a senior title on the
    profile page are dropped (enrich records that as a problem)."""
    by: dict[tuple, dict] = {}
    for p in rosters():
        for d in jl(DATA / "dossiers" / p.name):
            if d.get("heritage") != "chinese":
                continue
            pos = (d.get("position") or {}).get("value") or d.get("title_on_roster") or ""
            if pos and not young_title(pos):
                continue
            if any("senior title" in x for x in d.get("problems") or []):
                continue
            k = (d["name"].lower().strip(), d["institution"])
            if k in by:
                by[k]["departments"].append(d["department"])
                if not by[k].get("email") and d.get("email"):
                    by[k].update(email=d["email"])
                continue
            by[k] = {**d, "departments": [d["department"]], "title": pos}
    out = sorted(by.values(), key=lambda d: (d["institution"], d["name"]))
    for i, d in enumerate(out):
        d["id"] = f"b1-{i:04d}"
    return out


def card(d: dict) -> dict:
    res = (d.get("research") or {}).get("text") or ""
    quote = (d.get("position") or {}).get("evidence", {}).get("quote") or d.get("quote") or ""
    return {"id": d["id"], "name": d["name"], "institution": d["institution"],
            "department": "; ".join(dict.fromkeys(d["departments"])), "title": d["title"],
            "roster_text": quote[:300], "research": res[:700],
            "papers": [p["title"] for p in (d.get("papers") or [])[:3]]}


def cmd_cards(size: int) -> None:
    ps = people()
    (TAG / "in").mkdir(parents=True, exist_ok=True)
    (TAG / "out").mkdir(parents=True, exist_ok=True)
    (TAG / "people.jsonl").write_text("".join(json.dumps(p, default=str) + "\n" for p in ps))
    for i in range(0, len(ps), size):
        (TAG / "in" / f"b{i // size:02d}.jsonl").write_text("".join(json.dumps(card(p)) + "\n" for p in ps[i:i + size]))
    print(f"{len(ps)} people -> {(len(ps) + size - 1) // size} card files in data/tag/in/")


def coverage() -> list[dict]:
    t = targets()
    rows = []
    for inst in t["focus_schools"]:
        for g in jl(DATA / "grid" / f"{SLUG[inst]}.jsonl"):
            rows.append({"school": inst, "unit": g.get("unit"), "group": g.get("group"), "status": g.get("status"),
                         "roster_rows": g.get("rows"), "page_count": g.get("page_count"),
                         "url": "; ".join(g.get("urls") or []), "note": g.get("note", "")})
        for v in jl(DATA / "grid" / f"{SLUG[inst]}.verdicts.jsonl"):
            for r in rows:
                if r["school"] == inst and r["unit"] == v.get("unit"):
                    r["verifier"] = v.get("verdict")
    for inst in t.get("postponed_schools", []):
        rows.append({"school": inst, "unit": "(all)", "status": "postponed (applicant)",
                     "note": f"scouted: data/discovery/v3/{SLUG[inst]}.jsonl"})
    return rows


def cmd_export() -> None:
    import openpyxl
    ps = {p["id"]: p for p in jl(TAG / "people.jsonl")}
    tags = {t["id"]: t for f in sorted((TAG / "out").glob("*.jsonl")) for t in jl(f)}
    bad = {l.split("\t")[0] for l in (DATA / "validate_report.tsv").read_text().splitlines()} \
        if (DATA / "validate_report.tsv").exists() else set()
    order = {"A": 0, "B": 1, "?": 2, "C": 3}
    rows = defaultdict(list)
    for pid, p in ps.items():
        t = tags.get(pid, {"fit": "?"})
        em = (p.get("email") or {}).get("value")
        rec = {"School": p["institution"], "Department(s)": "; ".join(dict.fromkeys(p["departments"])), "Name": p["name"],
               "Title (official page)": p["title"], "Rank": position_class(p["title"]) if p["title"] else "",
               "Fit": t.get("fit"), "Theme": t.get("theme", ""), "Research (1 line)": t.get("summary", ""),
               "Hook (your project)": t.get("hook", ""), "Email": em or "",
               "Email source": (p.get("email") or {}).get("evidence", {}).get("source_url", ""),
               "Homepage": p.get("homepage") or p.get("profile_url") or "",
               "Paper 1": ((p.get("papers") or [{}])[0]).get("title", ""),
               "Paper 2": ((p.get("papers") or [{}, {}])[1:2] or [{}])[0].get("title", ""),
               "Official page": p.get("roster_url", ""), "Check": "associate: confirm promoted 2020+" if
               position_class(p["title"] or "") == "associate" else ""}
        sheet = "Dropped (C)" if t.get("fit") == "C" else ("Need email" if not em or pid in bad else "People")
        rows[sheet].append(rec)
    for v in rows.values():
        v.sort(key=lambda r: (order.get(r["Fit"], 2), r["Theme"], r["School"], r["Name"]))
    cshl = [r for r in jl(DATA / "roster" / "cshl-faculty.jsonl") if young_title(r.get("title_on_roster") or "")]
    rows["CSHL (any heritage)"] = [{"Name": r["name"], "Title (official page)": r["title_on_roster"],
                                   "Page": r.get("profile_url", "")} for r in cshl]
    rows["Coverage"] = coverage()
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name in ["People", "Need email", "Dropped (C)", "CSHL (any heritage)", "Coverage"]:
        ws = wb.create_sheet(name)
        data = rows.get(name, [])
        cols = list(dict.fromkeys(k for r in data for k in r)) or ["(empty)"]
        ws.append(cols)
        for r in data:
            ws.append([r.get(c, "") for c in cols])
        ws.freeze_panes = "A2"
    out = DATA / "export" / "batch1.xlsx"
    wb.save(out)
    print(out, {k: len(v) for k, v in rows.items()})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["rosters", "enrich", "cards", "export"])
    ap.add_argument("--size", type=int, default=40)
    a = ap.parse_args()
    if a.cmd == "rosters":
        for p in rosters():
            print(p)
    elif a.cmd == "enrich":
        cmd_enrich()
    elif a.cmd == "cards":
        cmd_cards(a.size)
    else:
        cmd_export()


if __name__ == "__main__":
    main()
