"""Record-level self-verification: an agent re-reads each professor's own page (agents/35_record_verifier.md) and code
checks that every quote it returns is really on the saved page. Passing records are the send-ready list; no human labels.

  python -m outreach.verify build data/export/list_v1_2026-11-02.xlsx   # People sheets -> data/verify/in/vNN.jsonl
  python -m outreach.verify check                                        # data/verify/out/*.jsonl -> data/verify/result.jsonl
  python -m outreach.verify sheet data/export/list_v1_2026-11-02.xlsx    # -> data/export/send_ready.xlsx

A record passes only if: at school, title is Assistant / Associate / incoming Assistant, the research quote is ML, an email
is on their own page with an official domain, nothing says "not taking students / don't email", and every quote is found
verbatim (whitespace / punctuation-insensitive) in the snapshot saved by outreach.fetch for that URL.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .batch1 import jl
from .config import ROOT, institution_domains
from .fetch import SNAP, emails, snapshot_path, visible_text
from .validate import norm_name

DATA = ROOT / "data"
V = DATA / "verify"
SHEETS = ("People", "People (batch 2)", "People (batch 3)", "Need email")
YOUNG_TITLE = re.compile(r"\b(assistant|associate)\s+(professor|prof\.?)\b|\basst\.?\s+prof|\bassoc\.?\s+prof", re.I)
NOT_YOUNG = re.compile(r"\b(adjunct|clinical|research|teaching|visiting|emerit|courtesy|affiliate)\b[^,;]*\bprofessor", re.I)
BLOCK = re.compile(r"not (currently )?(accepting|taking|recruiting)|no (new )?(phd )?students|do not (e-?mail|contact)|"
                   r"(don't|please don't) (e-?mail|contact)", re.I)


def norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(re.sub(r"[^a-z0-9@.]+", " ", s).split())


def page(url: str) -> tuple[str, str] | None:
    """(raw, visible text) of the snapshot fetch.py saved for url; manual saves in data/snapshots/manual/ also count."""
    if not url or not url.startswith("http"):
        return None
    p = snapshot_path(SNAP, url)
    if p.exists():
        raw = p.read_text(errors="ignore")
        return raw, visible_text(raw)
    return None


def quote_ok(url: str, quote: str) -> str:
    if not quote:
        return "empty quote"
    pg = page(url)
    if not pg:
        return f"no saved page for {url}"
    if norm(quote) not in norm(pg[1]) and norm(quote) not in norm(pg[0]):
        return f"quote not on page {url}"
    return ""


def by_name() -> dict:
    return {(norm_name(p["name"]), p["institution"]): p for p in jl(DATA / "tag" / "people.jsonl")}


def sheet_rows(xlsx: Path):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    for s in SHEETS:
        if s not in wb.sheetnames:
            continue
        rows = list(wb[s].iter_rows(values_only=True))
        for r in rows[1:]:
            d = dict(zip(rows[0], r))
            if d.get("Name"):
                yield s, d


SCHOOL = {"BU": "Boston University", "Duke": "Duke University", "USF": "University of South Florida", "UCSF":
          "University of California San Francisco", "CSHL": "Cold Spring Harbor Laboratory", "Mount Sinai":
          "Icahn School of Medicine at Mount Sinai", "JHU": "Johns Hopkins University", "UCF": "University of Central Florida",
          "Cornell": "Cornell University", "Rockefeller": "Rockefeller University"}


def find(d: dict, ix: dict) -> dict | None:
    sch = d.get("School") or ""
    for inst in (sch, SCHOOL.get(sch, "")):
        p = ix.get((norm_name(d["Name"]), inst))
        if p:
            return p
    cands = [p for (n, _), p in ix.items() if n == norm_name(d["Name"])]
    return cands[0] if len(cands) == 1 else None


def cmd_build(xlsx: Path, size: int = 12) -> None:
    ix = by_name()
    done = {o["id"] for f in (V / "out").glob("*.jsonl") for o in jl(f)}
    seen, rows, miss = set(), [], []
    for s, d in sheet_rows(xlsx):
        if s == "Need email" and d.get("Fit") not in ("A", "B"):
            continue
        p = find(d, ix)
        if not p:
            miss.append(d["Name"])
            continue
        if p["id"] in seen or p["id"] in done:
            continue
        seen.add(p["id"])
        rows.append({"id": p["id"], "name": p["name"], "institution": p["institution"], "title": d.get("Title (official page)"),
                     "email": d.get("Email") or None, "official_page": d.get("Official page") or p.get("profile_url"),
                     "lab_site": d.get("Homepage") or p.get("homepage")})
    (V / "in").mkdir(parents=True, exist_ok=True)
    (V / "out").mkdir(parents=True, exist_ok=True)
    k0 = len(list((V / "in").glob("*.jsonl")))
    for i in range(0, len(rows), size):
        (V / "in" / f"v{k0 + i // size:02d}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows[i:i + size]))
    print(f"{len(rows)} to verify -> data/verify/in/v{k0:02d}..; unmatched names: {miss}")


UNREAD = re.compile(r"403|404|forbidden|blocked|login|sign in|no (research )?(description|content|text)|could ?n.t|unable|"
                    r"not (load|read|available)|timeout|challenge", re.I)


def unread(c: dict) -> bool:
    """The agent could not read a page, as opposed to reading it and finding 'no'."""
    q = (c.get("quote") or "").strip()
    return not q or q.startswith("http") or bool(UNREAD.search(f"{q} {c.get('url') or ''}")) and len(q) < 120


def hard_validate_fail() -> set[str]:
    f = DATA / "validate_report.tsv"
    return {l.split("\t")[0] for l in f.read_text().splitlines() if l and not l.split("\t", 1)[1].startswith("WARN")} \
        if f.exists() else set()


BATCH3 = {"University of Washington", "University of California San Diego", "University of Maryland",
          "Georgia Institute of Technology", "University of California Irvine", "University of California Santa Cruz"}


def final_fits() -> dict:
    tag = DATA / "tag"
    fits = {t["id"]: t.get("fit") for f in sorted((tag / "out").glob("*.jsonl")) for t in jl(f)}
    fits.update({t["id"]: t.get("fit") for f in sorted((tag / "re_out").glob("*.jsonl")) for t in jl(f)})  # second opinion wins
    return fits


def cmd_build_tags(insts: set[str] = BATCH3, size: int = 12) -> None:
    """Batch 3 straight from tags: A, B and '?' (no readable text yet; the verifier reads the page and decides)."""
    fits = final_fits()
    done = {r["id"] for f in (V / "in").glob("*.jsonl") for r in jl(f)}
    rows = [{"id": p["id"], "name": p["name"], "institution": p["institution"], "title": p.get("title"),
             "email": p.get("email"), "official_page": p.get("profile_url") or p.get("roster_url"),
             "lab_site": p.get("homepage"), "department": "; ".join(dict.fromkeys(p.get("departments") or []))}
            for p in jl(DATA / "tag" / "people.jsonl")
            if p["institution"] in insts and fits.get(p["id"]) in ("A", "B", "?") and p["id"] not in done]
    rows.sort(key=lambda r: {"A": 0, "B": 1}.get(fits.get(r["id"]), 2))   # A/B first: send-ready sooner
    k0 = len(list((V / "in").glob("w*.jsonl")))
    for i in range(0, len(rows), size):
        (V / "in" / f"w{k0 + i // size:02d}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows[i:i + size]))
    print(f"{len(rows)} batch-3 records -> data/verify/in/w{k0:02d}..")


def judge(o: dict, inst: str, rec: dict | None = None) -> tuple[bool, list[str], str | None]:
    why = []
    for k in ("at_school", "title", "does_ml"):
        c = o.get(k) or {}
        if not c.get("ok") and unread(c):
            why.append(f"unread {k}: {(c.get('quote') or c.get('url') or '')[:80]}")
        elif not c.get("ok"):
            why.append(f"{k}: agent says no ({(c.get('quote') or c.get('url') or '')[:80]})")
        elif (e := quote_ok(c.get("url", ""), c.get("quote", ""))):
            why.append(f"{k}: {e}")
    t = o.get("title") or {}
    tv = f'{t.get("value") or ""} {t.get("quote") or ""}'
    if t.get("ok") and (not YOUNG_TITLE.search(tv) and "incoming" not in tv.lower() or NOT_YOUNG.search(t.get("value") or "")):
        why.append(f"title: not assistant/associate ({t.get('value')})")
    nb = o.get("no_block") or {}
    if not nb.get("ok") and unread(nb):   # empty quote = the agent could not read the page, not a refusal
        why.append(f"unread no_block: {(nb.get('url') or '')[:80]}")
    elif not nb.get("ok"):
        why.append(f"no_block: {(nb.get('quote') or '')[:100]}")
    elif nb.get("quote") and BLOCK.search(nb["quote"]):
        why.append(f"no_block: quote says {nb['quote'][:80]}")
    em = (o.get("email") or {})
    val = (em.get("value") or "").strip().lower() or None
    rec = rec or {}
    if isinstance(rec.get("email"), dict):   # enrich stores {"value", "evidence"}
        rec = {**rec, "email": rec["email"].get("value")}
    if not val and rec.get("email") and rec["id"] not in hard_validate_fail():
        val = str(rec["email"]).lower()   # found earlier on an official directory page; validate.py checked the snapshot
    elif not val:
        why.append("email: not found on own page")
    else:
        pg = page(em.get("url", ""))
        if not pg:
            why.append(f"email: no saved page for {em.get('url')}")
        elif val not in {e for e, _ in emails(pg[0])}:
            why.append(f"email: {val} not on {em.get('url')}")
        doms = institution_domains(inst)
        dom = val.split("@")[-1]
        if doms and not any(dom == x or dom.endswith("." + x) for x in doms):
            why.append(f"email: domain {dom} not official {doms}")
    return not why, why, val


def cmd_check() -> None:
    ins = {r["id"]: r for f in (V / "in").glob("*.jsonl") for r in jl(f)}
    res = []
    outs = sorted((V / "out").glob("*.jsonl"), key=lambda f: (f.name.startswith("retry"), f.name))   # retry pass wins
    for f in outs:
        for o in jl(f):
            r = ins.get(o.get("id"))
            if not r:
                continue
            ok, why, em = judge(o, r["institution"], r)
            res.append({"id": r["id"], "name": r["name"], "institution": r["institution"], "pass": ok, "why": why,
                        "email": em, "email_changed": bool(em and r.get("email") and em != str((r["email"] or {}).get("value") if isinstance(r["email"], dict) else r["email"]).lower()),
                        "title": (o.get("title") or {}).get("value"), "ml_quote": (o.get("does_ml") or {}).get("quote"),
                        "official_page": (o.get("at_school") or {}).get("url")})
    res = list({x["id"]: x for x in res}.values())
    (V / "result.jsonl").write_text("".join(json.dumps(x) + "\n" for x in res))
    todo = sorted(set(ins) - {x["id"] for x in res})
    print(f"verified {len(res)}/{len(ins)}: pass {sum(x['pass'] for x in res)}, fail {sum(not x['pass'] for x in res)}, "
          f"email corrected {sum(x['email_changed'] for x in res)}; not yet verified {len(todo)}")
    from collections import Counter
    print("fail reasons:", Counter(w.split(":")[0] for x in res for w in x["why"]).most_common())


CLINICAL = re.compile(r"\b(medicine|neurology|neurosurgery|surgery|pediatrics|ophthalmology|psychiatry|anesthesiology|"
                      r"nephrology|cardiology|oncology|dermatology|urology|obstetrics|orthopa\w*|emergency)\b", re.I)
NONCLINICAL = re.compile(r"statist|bioinformatic|informatic|engineering|computer|computing|data|artificial intelligence|\bAI\b|"
                         r"mathemat|genetic|genomic|neuroscience|biology", re.I)


def scope_problem(title: str) -> str:
    """Applicant's scope rules applied to the verified title (targets.yaml exclude_units): clinical-only appointments
    and business-only appointments are out; a joint appointment with a non-clinical / non-business unit stays."""
    from .batch1 import BUSINESS
    t = re.sub(r"school of medicine|college of medicine|(icahn|weill)[^,;|]*", "", title, flags=re.I)
    if CLINICAL.search(t) and not NONCLINICAL.search(t):
        return f"scope: clinical-department appointment ({title[:60]})"
    if BUSINESS.search(t) and not NONCLINICAL.search(t):
        return f"scope: business-school appointment ({title[:60]})"
    return ""


def cmd_sheet(xlsx: Path) -> None:
    """Send-ready list = verified records, ranked by the applicant's priority rules (batch1.priority + dblp bump),
    then 'recruiting' on their own page, then top-ML papers. Extra columns from the earlier export when present."""
    import openpyxl
    from .batch1 import priority
    ix = by_name()
    ps = {p["id"]: p for p in jl(DATA / "tag" / "people.jsonl")}
    tag = DATA / "tag"
    tags = {t["id"]: t for f in sorted((tag / "out").glob("*.jsonl")) for t in jl(f)}
    tags.update({t["id"]: t for f in sorted((tag / "re_out").glob("*.jsonl")) for t in jl(f)})
    for r in jl(tag / "retheme_out.jsonl"):
        if r["id"] in tags and r.get("theme"):
            tags[r["id"]]["theme"] = r["theme"]
    dblp = {d["id"]: d for d in jl(DATA / "dblp.jsonl")}
    old = {}
    if xlsx.exists():
        for _, d in sheet_rows(xlsx):
            p = find(d, ix)
            if p:
                old.setdefault(p["id"], d)
    ready, failed = [], []
    for x in jl(V / "result.jsonl"):
        p, t, db, o = ps.get(x["id"], {}), tags.get(x["id"], {}), dblp.get(x["id"], {}), old.get(x["id"], {})
        pr = priority(t.get("theme", ""), set(p.get("groups") or []))
        if (db.get("ml_top") or 0) >= 3:
            pr = max(1, pr - 1)
        rec = {"Priority": pr, "School": x["institution"], "Department(s)": "; ".join(dict.fromkeys(p.get("departments") or [])),
               "Name": x["name"], "Title (verified)": x["title"], "Theme": t.get("theme", ""),
               "Top-ML papers 2023-26 (dblp)": db.get("ml_top", "") if db.get("pid") else "",
               "Email (verified)": x["email"], "Research (own words)": x["ml_quote"], "Official page": x["official_page"],
               "Lab site": p.get("homepage") or o.get("Homepage"), "Recruiting (own words)": o.get("Recruiting (own words)"),
               "How they want to be contacted": o.get("How they want to be contacted (own words)"),
               "Hook (your project)": o.get("Hook (your project)") or t.get("hook", ""), "id": x["id"]}
        scope = scope_problem(x.get("title") or "")
        if x["pass"] and not scope:
            ready.append(rec)
        elif x["pass"]:
            failed.append({**rec, "Why not": scope})
        else:
            failed.append({**rec, "Why not": "; ".join(x["why"])})
    ready.sort(key=lambda r: (r["Priority"], not r["Recruiting (own words)"], -(r["Top-ML papers 2023-26 (dblp)"] or 0)))
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    no_email = [r for r in failed if r["Why not"] and all(w.strip().startswith("email") for w in r["Why not"].split(";"))]
    failed = [r for r in failed if r not in no_email]
    no_email.sort(key=lambda r: (r["Priority"], -(r["Top-ML papers 2023-26 (dblp)"] or 0)))
    for name, rs in (("Send-ready (verified)", ready), ("Verified, no official email", no_email),
                     ("Failed verification", failed)):
        ws = wb.create_sheet(name)
        cols = list(dict.fromkeys(k for r in rs for k in r)) or ["Name"]
        ws.append(cols)
        for r in rs:
            ws.append([r.get(c) for c in cols])
    out = DATA / "export" / "send_ready.xlsx"
    wb.save(out)
    print(f"{len(ready)} send-ready, {len(no_email)} verified without official email, {len(failed)} failed -> {out}")


def cmd_retry(size: int = 10) -> None:
    """Records the agent could not read (blocked / empty official page) -> new input files for a second pass that
    must try the lab site and other official pages."""
    ins = {r["id"]: r for f in (V / "in").glob("*.jsonl") for r in jl(f)}
    done_retry = {r["id"] for f in (V / "in").glob("retry*.jsonl") for r in jl(f)}
    ids = [x["id"] for x in jl(V / "result.jsonl") if not x["pass"] and any(w.startswith("unread") for w in x["why"])
           and x["id"] not in done_retry]
    k0 = len(list((V / "in").glob("retry*.jsonl")))
    for i in range(0, len(ids), size):
        (V / "in" / f"retry{k0 + i // size:02d}.jsonl").write_text("".join(json.dumps({**ins[j], "retry": True}) + "\n"
                                                                         for j in ids[i:i + size]))
    print(f"{len(ids)} unread records -> data/verify/in/retry{k0:02d}..")


def main() -> None:
    cmd, *rest = sys.argv[1:] or ["check"]
    if cmd == "build":
        cmd_build(Path(rest[0]))
    elif cmd == "check":
        cmd_check()
    elif cmd == "build-tags":
        cmd_build_tags()
    elif cmd == "retry":
        cmd_retry()
    elif cmd == "sheet":
        cmd_sheet(Path(rest[0]))


if __name__ == "__main__":
    main()
