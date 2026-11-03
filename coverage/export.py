"""Usable advisor list now: `python -m coverage.export [--no-fetch]` -> data/export/advisors_v2.xlsx.

Sheet "Advisors": one row per ledger person who is `listed` or fit-judged A/B (or judges disagree on fit), sorted by the
applicant's priority (config/targets.yaml `priority`, +1 tier for >=3 top-ML papers 2023-26, recruiting, A before B).
Sheet "Not done": schools with open BIG units, recall misses, open:title people, items waiting on the human, and the
count of people still waiting for fit judges (from coverage.check).

evidence status: verified-earlier (record verifier passed, email on an official page) | fit-judged-not-record-verified
(two judges A/B, quotes not yet checked on snapshots) | judges-disagree (fit '?').
Email: only a verbatim address from the verifier, a dossier (own/official page + url) or outreach.enrich.pick_email on the
person's cached/fetched profile or own page. Never guessed.
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

from . import scope
from .scope import DATA, jl

OUT = DATA / "export" / "advisors_v2.xlsx"
COLS = ["school", "department(s)", "name", "title", "fit", "theme", "judges", "summary", "hook (applicant project)",
        "email", "email source", "homepage", "evidence status", "priority"]
NOT_DONE_COLS = ["kind", "school", "item", "detail"]


def _key(school, name):
    return (school, scope.name_key(name))


def roster_groups() -> dict[str, str]:
    """roster file basename -> grid group (G1 CS-type ML, G2 AI dept / initiative, G3 molecular, G4 neuro)."""
    out = {}
    for f in glob.glob(str(DATA / "grid" / "*.jsonl")):
        if f.endswith(".units.jsonl"):
            continue
        for g in jl(f):
            if g.get("roster"):
                out[Path(g["roster"]).name] = str(g.get("group") or "")
    return out


def priority(theme: str, groups: set[str], ml_top: int = 0) -> int:
    """1 NeuroAI / trustworthy-ML, 2 AI dept / initiative (G2), 3 CS-type ML (G1), 4 molecular / bio ML (G3);
    >=3 top-ML papers 2023-26 moves up one tier."""
    if theme in ("NeuroAI", "trustworthy-ML"):
        p = 1
    elif any("G2" in g for g in groups):
        p = 2
    elif any("G1" in g for g in groups) or theme in ("core-ML/CV", "stats-methods"):
        p = 3
    else:
        p = 4
    return max(1, p - 1) if ml_top >= 3 else p


def load_sources() -> dict:
    """Existing data keyed by (school, name_key): tags (older pipeline), decided (coverage.fit), verify, dossier, dblp."""
    tag_people = {p["id"]: p for p in jl(DATA / "tag" / "people.jsonl") if p.get("id")}

    def k_of(p):
        return _key(scope.school_of(p.get("institution") or "") or p.get("institution"), p.get("name") or "")
    tags, verify, dblp, dossier, decided = {}, {}, {}, {}, {}
    for f in sorted(glob.glob(str(DATA / "tag" / "out" / "*.jsonl"))):
        for t in jl(f):
            if t.get("id") in tag_people:
                tags[k_of(tag_people[t["id"]])] = t
    for v in jl(DATA / "verify" / "result.jsonl"):
        verify[k_of(tag_people.get(v["id"]) or v)] = v
    for d in jl(DATA / "dblp.jsonl"):
        if d.get("id") in tag_people:
            dblp[k_of(tag_people[d["id"]])] = d
    for f in sorted(glob.glob(str(DATA / "dossiers" / "*.jsonl"))):
        for d in jl(f):
            dossier.setdefault(_key(scope.school_of(d.get("institution") or "") or d.get("institution"), d.get("name") or ""), d)
    for d in jl(DATA / "fit" / "decided.jsonl"):
        decided[_key(d["school"], d["name"])] = d
    return {"tags": tags, "verify": verify, "dblp": dblp, "dossier": dossier, "decided": decided, "groups": roster_groups()}


def find_email(row: dict, dossier: dict | None, fetch: bool) -> tuple[str, str]:
    """(email, source url) verbatim from an official page or the person's own page; ('', '') if none."""
    e = (dossier or {}).get("email") or {}
    if isinstance(e, dict) and e.get("value"):
        return e["value"], e.get("url") or (e.get("evidence") or {}).get("source_url") or ""
    if not fetch:
        return "", ""
    try:
        from outreach.enrich import pick_email, pick_links
        from outreach.fetch import get
        url = row.get("profile_url")
        if not url or url.startswith("mailto:"):
            return "", ""
        raw = get(url)
        hit = pick_email(raw, url, row["name"], row["school"])
        if hit:
            return hit["value"], url
        links = pick_links(raw, url, row["name"])
        for u in dict.fromkeys(x for x in (links.get("homepage"), links.get("lab_website")) if x):
            try:
                hit = pick_email(get(u), u, row["name"], row["school"], own_page=True)
            except Exception:
                continue
            if hit:
                return hit["value"], u
    except Exception:
        pass
    return "", ""


def _recruit(rec) -> int:
    """0 own site says recruiting, 1 says nothing useful, 2 says not recruiting (sorts last within a tier)."""
    st = [x.get("status") for x in (rec if isinstance(rec, list) else [rec] if isinstance(rec, dict) else []) if isinstance(x, dict)]
    return 0 if "Yes" in st else 2 if "No" in st else 1


def build_rows(ledger: list[dict], src: dict, fetch: bool = True) -> list[dict]:
    rows = []
    for r in ledger:
        if not r.get("in_scope"):
            continue
        k = _key(r["school"], r["name"])
        dec = src["decided"].get(k)
        ver = src["verify"].get(k)
        tag = src["tags"].get(k) or {}
        listed = r.get("outcome") == "listed"
        disagree = bool(dec and (dec.get("note") or dec.get("fit") == "?"))
        fit = (dec or {}).get("fit") or r.get("fit") or tag.get("fit")
        if not (listed or fit in ("A", "B") or disagree):
            continue
        if r.get("outcome", "").startswith("rejected"):
            continue
        d = src["dossier"].get(k)
        meta = dec or tag
        theme = meta.get("theme", "")
        db = src["dblp"].get(k) or {}
        groups = {src["groups"].get(s, "") for s in r.get("sources") or []}
        if listed:
            status, judges = "verified-earlier", "earlier pipeline"
        elif disagree:
            status, judges = "judges-disagree", "disagree"
        else:
            status, judges = "fit-judged-not-record-verified", "agree" if dec else "earlier pipeline"
        email, esrc = ((ver or {}).get("email") or "", (ver or {}).get("official_page") or r.get("profile_url") or "") \
            if listed and (ver or {}).get("email") else find_email(r, d, fetch)
        rows.append({
            "school": r["school"], "department(s)": "; ".join(dict.fromkeys(r.get("units") or [])), "name": r["name"],
            "title": (ver or {}).get("title") or r.get("title") or "", "fit": fit or "", "theme": theme, "judges": judges,
            "summary": meta.get("summary", "") + (f" [{dec['note']}]" if dec and dec.get("note") else ""),
            "hook (applicant project)": meta.get("hook", ""), "email": email, "email source": esrc if email else "",
            "homepage": (d or {}).get("lab_website") or (d or {}).get("homepage") or r.get("profile_url") or "",
            "evidence status": status, "priority": priority(theme, groups, db.get("ml_top") or 0),
            "_recruit": _recruit((d or {}).get("recruiting")),
            "_ml": -(db.get("ml_top") or 0)})
    rows.sort(key=lambda x: (x["priority"], x["_recruit"], x["_ml"], {"A": 0, "B": 1}.get(x["fit"], 2), x["school"], x["name"]))
    return rows


def not_done(ledger: list[dict]) -> list[dict]:
    """Rows for the second sheet, from coverage.check's own functions."""
    from . import check
    out = []
    reqs = check.human_requests()
    missing = check.recall(ledger)
    for s in scope.schools():
        for x in check.units(s):
            kind = "waiting on human" if check._waits_unit(s, x, reqs) else "open big unit"
            out.append({"kind": kind, "school": s, "item": x.split(":")[0], "detail": x})
        for m in missing.values():
            if m["school"] == s:
                kind = "waiting on human" if check._waits_person(s, m["name"], reqs) else "recall miss"
                out.append({"kind": kind, "school": s, "item": m["name"], "detail": f"found by {sorted(m['probes'])} {m.get('url') or ''}"})
        n_fit = 0
        for r in ledger:
            if r["school"] != s or not r.get("in_scope"):
                continue
            o = str(r.get("outcome"))
            if o.startswith("open:title"):
                out.append({"kind": "open:title", "school": s, "item": r["name"], "detail": f"{r.get('title', '')[:80]} | needs official title"})
            elif o == "open":
                n_fit += 1
        if n_fit:
            out.append({"kind": "awaiting fit judges", "school": s, "item": f"{n_fit} people", "detail": "cards in data/fit/batches"})
    return out


def write_xlsx(rows: list[dict], nd: list[dict], path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    for title, cols, data in (("Advisors", COLS, rows), ("Not done", NOT_DONE_COLS, nd)):
        ws = wb.active if title == "Advisors" else wb.create_sheet(title)
        ws.title = title
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in data:
            ws.append([r.get(c, "") for c in cols])
        ws.freeze_panes = "A2"
        for i, c in enumerate(cols, 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = 60 if c in ("summary", "detail", "hook (applicant project)") else 24
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    ledger = jl(DATA / "coverage" / "people.jsonl")
    rows = build_rows(ledger, load_sources(), not a.no_fetch)
    nd = not_done(ledger)
    write_xlsx(rows, nd, OUT)
    from collections import Counter
    print(f"{len(rows)} advisors, {len(nd)} not-done items -> {OUT}; status {dict(Counter(r['evidence status'] for r in rows))}; "
          f"with email {sum(1 for r in rows if r['email'])}")


if __name__ == "__main__":
    main()
