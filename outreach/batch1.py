"""Batch 1 glue: grid rosters -> enrich (young + Chinese surname only) -> tagger cards -> batch1.xlsx.

  python -m outreach.batch1 rosters          # roster files of the focus schools, from data/grid/*.jsonl
  python -m outreach.batch1 enrich           # enrich.py --heritage chinese on each (young titles only)
  python -m outreach.batch1 cards [--size 40]  # data/tag/in/bNN.jsonl for agents/26_fit_tagger.md
  python -m outreach.batch1 export           # data/export/batch1.xlsx (+ csv)
"""
from __future__ import annotations

import argparse
import json
import re
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


def roster_groups() -> dict[str, str]:
    """roster file name -> grid group (G1 AI core, G2 AI dept/initiative, G3 molecular/biomed, G4 neuro)."""
    return {Path(g["roster"]).name: str(g.get("group", "")) for g in grid() if g.get("roster")}


def priority(theme: str, groups: set[str]) -> int:
    """Applicant's order (config/targets.yaml `priority`): NeuroAI, then AI departments / initiatives,
    then CS-type ML, then molecular / bio ML."""
    if theme == "NeuroAI":
        return 1
    if any("G2" in g for g in groups):
        return 2
    if any("G1" in g for g in groups) or theme in ("core-ML/CV", "stats-methods"):
        return 3
    return 4


def people() -> list[dict]:
    """One record per person (name + institution); departments merged. Dossier rows with a senior title on the
    profile page are dropped (enrich records that as a problem)."""
    by: dict[tuple, dict] = {}
    grp = roster_groups()
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
                by[k]["groups"].append(grp.get(p.name, ""))
                if not by[k].get("email") and d.get("email"):
                    by[k].update(email=d["email"])
                continue
            by[k] = {**d, "departments": [d["department"]], "groups": [grp.get(p.name, "")], "title": pos}
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


def page_text(url: str, name: str, n: int = 1500) -> str:
    """Visible text of a saved snapshot, starting near the person's surname (no new fetch)."""
    from .fetch import SNAP, snapshot_path, visible_text
    if not url:
        return ""
    sp = snapshot_path(SNAP, url)
    if not sp.exists():
        return ""
    v = visible_text(sp.read_text(errors="ignore"))
    i = v.lower().find(name.split()[-1].lower())
    return v[max(0, i - 100): max(0, i - 100) + n]


def cmd_recards(ids_file: Path, size: int) -> None:
    """Second-opinion cards: the first card plus profile / homepage text from saved snapshots."""
    want = json.loads(ids_file.read_text())
    ids = [i for v in want.values() for i in v]
    ps = {p["id"]: p for p in jl(TAG / "people.jsonl")}
    (TAG / "re_in").mkdir(parents=True, exist_ok=True)
    (TAG / "re_out").mkdir(parents=True, exist_ok=True)
    cards = []
    for i in ids:
        p = ps[i]
        c = card(p)
        c["profile_text"] = page_text(p.get("profile_url") or "", p["name"])
        hp = p.get("homepage") or ""
        c["homepage_text"] = page_text(hp, p["name"]) if hp and hp != p.get("profile_url") else ""
        c["papers"] = [x["title"] for x in (p.get("papers") or [])[:6]]
        cards.append(c)
    for k in range(0, len(cards), size):
        (TAG / "re_in" / f"r{k // size:02d}.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cards[k:k + size]))
    print(f"{len(cards)} recheck cards -> data/tag/re_in/")


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
                    r["verifier (first pass)"] = v.get("verdict")
                    r["after fix"] = ("re-built; every person the verifier named as missing is now present (code check)"
                                      if v.get("verdict") in ("FAIL", "FIXABLE") else "")
    for inst in t.get("postponed_schools", []):
        rows.append({"school": inst, "unit": "(all)", "status": "postponed (applicant)",
                     "note": f"scouted: data/discovery/v3/{SLUG[inst]}.jsonl"})
    return rows


# ---- export-time cleanup (auditor 2026-10-31); ids in data/tag/people.jsonl stay frozen ----
JUNK_URL = re.compile(r"terms-of-use|faculty-resources/handbook|omniupdate|safelinks|a-lab-like-no-other|"
                      r"/login|wp-admin", re.I)
BOILER = re.compile(r"physicians and scientists on the faculty of the icahn school", re.I)
NOT_ADVISING = re.compile(r"of instruction|of the practice|teaching|affiliate|lecturer|instructor", re.I)


def clean(ps: list[dict]) -> None:
    """Blank homepages that are site boilerplate or shared by >2 people; drop boilerplate research text."""
    from collections import Counter
    n = Counter((p.get("homepage") or "").rstrip("/") for p in ps)
    for p in ps:
        hp = (p.get("homepage") or "").rstrip("/")
        if hp and (JUNK_URL.search(hp) or n[hp] > 2):
            p["homepage"] = ""
        r = p.get("research") or {}
        if BOILER.search(r.get("text") or ""):
            p["research"] = {}


def dedupe(ps: list[dict], tags: dict) -> list[dict]:
    """Same person listed under two names (e.g. "Jason Ji" = Zhicheng Ji): same profile URL, homepage or
    email local part at one institution. Keep the copy with an email; merge departments."""
    from .validate import norm_name

    def keyof(p: dict) -> set[str]:
        slug = norm_name(re.sub(r"[._\-]+", " ", (p.get("profile_url") or "").rstrip("/").rsplit("/", 1)[-1]))
        ks = {(p.get("profile_url") or "").rstrip("/").lower(), (p.get("homepage") or "").rstrip("/").lower(),
              ((p.get("email") or {}).get("value") or "").split("@")[0].lower(), "n:" + norm_name(p["name"])}
        if len(slug.split()) >= 2:
            ks.add("n:" + slug)   # profile URL slug is a name: ".../person/Zhicheng.Ji" vs listed as "Jason Ji"
        return {k for k in ks if k and k != "n:"}
    out: list[dict] = []
    for p in sorted(ps, key=lambda p: not (p.get("email") or {}).get("value")):
        hit = next((q for q in out if q["institution"] == p["institution"] and keyof(q) & keyof(p)), None)
        if hit:
            hit["departments"] = list(dict.fromkeys(hit["departments"] + p["departments"]))
            hit["groups"] = list(dict.fromkeys(hit.get("groups", []) + p.get("groups", [])))
            hit.setdefault("aka", []).append(p["name"])
            if tags.get(p["id"], {}).get("fit", "?") < tags.get(hit["id"], {}).get("fit", "?"):
                tags[hit["id"]] = tags[p["id"]]
        else:
            out.append(p)
    return out


def own_text(p: dict) -> str:
    from .fetch import SNAP, snapshot_path, visible_text
    t = []
    for u in {p.get("profile_url"), p.get("homepage"), p.get("pubs"), p.get("roster_url")}:
        sp = snapshot_path(SNAP, u) if u else None
        if sp and sp.exists():
            t.append(visible_text(sp.read_text(errors="ignore")).lower())
    return " ".join(t)


def split_papers(p: dict) -> tuple[list[str], list[str]]:
    """Confirmed = the title is on the person's own saved page; name+affiliation matches alone are unconfirmed
    (Europe PMC / S2 can return a same-name author at the same school)."""
    txt = own_text(p)
    norm = lambda s: " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())
    nt = norm(txt)
    conf, unconf = [], []
    for x in p.get("papers") or []:
        (conf if norm(x["title"])[:60] and norm(x["title"])[:60] in nt else unconf).append(f'{x["title"]} ({x.get("year", "")})')
    return conf, unconf


def evidence(p: dict, card_re: dict) -> str:
    """strong = research text / a paper confirmed on the own page / real profile text; weak = only papers
    matched by name + affiliation (may be a same-name author); none."""
    r = (p.get("research") or {}).get("text") or ""
    prof = card_re.get("profile_text", "")
    if len(r) > 80 or split_papers(p)[0] or (len(prof) > 300 and not BOILER.search(prof)):
        return "strong"
    return "weak" if p.get("papers") else "none"


def check_note(p: dict) -> str:
    notes = []
    if position_class(p["title"] or "") == "associate":
        notes.append("associate: confirm promoted 2020+")
    if "epidemiology" in (p["title"] + " " + (p.get("quote") or "")).lower():
        notes.append("appointment in Epidemiology & Biostatistics (excluded dept): your call")
    if p.get("_weak"):
        notes.append("fit based on name-matched papers only: check they are this person's")
    if p.get("aka"):
        notes.append(f"also listed as {', '.join(p['aka'])}")
    return "; ".join(notes)


def cmd_validate() -> None:
    """Deterministic email checks (same rules as validate.py): the address is on its saved source page,
    on an official domain (else WARN), plausibly the person's, and not shared by two people."""
    from .config import institution_domains
    from .fetch import SNAP, visible_text
    from .validate import email_appears_in, norm_name, snapshot_text
    out, seen = [], defaultdict(list)
    for p in jl(TAG / "people.jsonl"):
        e = p.get("email") or {}
        em = (e.get("value") or "").lower()
        if not em:
            continue
        seen[em].append(p["id"])
        snap = snapshot_text(SNAP, e.get("evidence", {}).get("source_url", ""))
        if snap is None:
            out.append((p["id"], "email source page has no saved snapshot"))
        elif not (email_appears_in(em, snap) or email_appears_in(em, visible_text(snap))):
            out.append((p["id"], "email not found in saved snapshot of its source page"))
        doms = institution_domains(p["institution"])
        dom = em.split("@", 1)[1]
        if doms and not any(dom == d or dom.endswith("." + d) for d in doms):
            out.append((p["id"], f"WARN email domain {dom} not in {doms}"))
        toks = [t for t in norm_name(p["name"]).split() if len(t) >= 3]
        local = em.split("@")[0]
        ini = "".join(t[0] for t in norm_name(p["name"]).split())
        if not any(t in local for t in toks) and not local.startswith(ini[:2]):
            out.append((p["id"], f"WARN email local part {local} does not resemble the name"))
    out += [(i, f"email {em} shared by {ids}") for em, ids in seen.items() if len(ids) > 1 for i in ids]
    (DATA / "validate_report.tsv").write_text("".join(f"{i}\t{m}\n" for i, m in out))
    print(f"{len(out)} problems ({sum(not m.startswith('WARN') for _, m in out)} hard) -> data/validate_report.tsv")


def cmd_export() -> None:
    import openpyxl
    raw = jl(TAG / "people.jsonl")
    tags = {t["id"]: t for f in sorted((TAG / "out").glob("*.jsonl")) for t in jl(f)}
    tags.update({t["id"]: t for f in sorted((TAG / "re_out").glob("*.jsonl")) for t in jl(f)})   # second opinion wins
    recard = {c["id"]: c for f in sorted((TAG / "re_in").glob("*.jsonl")) for c in jl(f)}
    clean(raw)
    ps = {p["id"]: p for p in dedupe(raw, tags)}
    bad = {l.split("\t")[0] for l in (DATA / "validate_report.tsv").read_text().splitlines()
           if l and not l.split("\t", 1)[1].startswith("WARN")} if (DATA / "validate_report.tsv").exists() else set()
    order = {"A": 0, "B": 1, "?": 2, "C": 3}
    rows = defaultdict(list)
    for pid, p in ps.items():
        t = dict(tags.get(pid, {"fit": "?"}))
        ev = evidence(p, recard.get(pid, {}))
        if t.get("fit") in ("A", "B", "C") and ev == "none":
            t["fit"], t["summary"] = "?", f"(no research evidence saved) {t.get('summary', '')}"
        elif t.get("fit") in ("A", "B") and ev == "weak":
            p["_weak"] = True
        conf, unconf = split_papers(p)
        em = (p.get("email") or {}).get("value")
        rec = {"Priority": priority(t.get("theme", ""), set(p.get("groups") or [])), "School": p["institution"], "Department(s)": "; ".join(dict.fromkeys(p["departments"])), "Name": p["name"],
               "Title (official page)": p["title"], "Rank": position_class(p["title"]) if p["title"] else "",
               "Fit": t.get("fit"), "Theme": t.get("theme", ""), "Research (1 line)": t.get("summary", ""),
               "Hook (your project)": t.get("hook", ""), "Email": em or "",
               "Email source": (p.get("email") or {}).get("evidence", {}).get("source_url", ""),
               "Homepage": p.get("homepage") or p.get("profile_url") or "",
               "Paper 1 (on own page)": conf[0] if conf else "", "Paper 2 (on own page)": conf[1] if len(conf) > 1 else "",
               "Papers by name match (check author)": " | ".join(unconf[:2]),
               "Official page": p.get("roster_url", ""), "Check": check_note(p)}
        if t.get("fit") == "C":
            sheet = "Dropped (C)"
        elif not p["title"] or NOT_ADVISING.search(p["title"]) or t.get("fit") == "?":
            sheet = "Check (title or fit)"
        else:
            sheet = "Need email" if not em or pid in bad else "People"
        rows[sheet].append(rec)
    for v in rows.values():
        v.sort(key=lambda r: (r.get("Priority", 9), order.get(r.get("Fit"), 2), r.get("School", ""), r.get("Name", "")))
    cshl = [r for r in jl(DATA / "roster" / "cshl-faculty.jsonl") if young_title(r.get("title_on_roster") or "")]
    rows["CSHL (any heritage)"] = [{"Name": r["name"], "Title (official page)": r["title_on_roster"],
                                   "Page": r.get("profile_url", "")} for r in cshl]
    summary = []
    for inst in targets()["focus_schools"]:
        k = lambda sh: sum(r.get("School") == inst for r in rows.get(sh, []))
        summary.append({"school": inst, "unit": "(school total)", "status":
                        f"people {k('People')} | need email {k('Need email')} | check {k('Check (title or fit)')} | dropped C {k('Dropped (C)')}"})
    rows["Coverage"] = summary + coverage()
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name in ["People", "Need email", "Check (title or fit)", "Dropped (C)", "CSHL (any heritage)", "Coverage"]:
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
    ap.add_argument("cmd", choices=["rosters", "enrich", "cards", "recards", "validate", "export"])
    ap.add_argument("--size", type=int, default=40)
    ap.add_argument("--ids", type=Path, help="recards: JSON {group: [ids]}")
    a = ap.parse_args()
    if a.cmd == "rosters":
        for p in rosters():
            print(p)
    elif a.cmd == "enrich":
        cmd_enrich()
    elif a.cmd == "cards":
        cmd_cards(a.size)
    elif a.cmd == "recards":
        cmd_recards(a.ids, a.size)
    elif a.cmd == "validate":
        cmd_validate()
    else:
        cmd_export()


if __name__ == "__main__":
    main()
