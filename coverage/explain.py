"""Record why a probe hit is legitimately not in the people ledger (data/coverage/explained.jsonl).

  python -m coverage.explain --school "Cornell University" --name "Yudong Chen" --reason moved_institution \
      --evidence https://pages.cs.wisc.edu/~yudongchen/ --to "Wisconsin" --quote "Lubar Professor, University of Wisconsin-Madison"

Reasons (closed vocabulary; anything else is refused):
  moved_institution       now at another school: --to NAME, and the quote on the new page must name it
  senior_title            full professor / chair / emeritus: cannot be young: --title T, the quote must contain it
  not_phd_advising_title  teaching / research-track / lecturer / staff scientist: --title T, the quote must contain it
  postdoc_pre_independent NIH K99 (mentored phase): evidence = RePORTER project; the tool queries RePORTER itself and
                          requires an active K99 (fiscal year >= current FY - 1) at that school and no R00 for the PI
  clinical_unit           clinical department / hospital-only appointment: --unit NAME, the quote must contain it
  out_of_scope_unit       faculty in a unit the targets do not cover: --unit NAME, the quote must contain it
                          (clinical/out_of_scope evidence may not be nsf.gov / nih.gov: those APIs carry no department)
  alias_of_ledger         the probe uses another spelling of someone IS in the ledger: --note "same as <ledger name>"
Every other reason needs --quote: verbatim text of the evidence page. The tool fetches the page (snapshot) and refuses
unless the quote is in it (case/whitespace-insensitive). The row stores quote + fetched date. coverage.check counts only
rows with a verified quote; legacy rows show as "unproven exclusion". `--validate [--school S]` re-checks stored rows
offline (snapshots when present). `--dry-run` verifies and prints without writing.
Never explain a person away with "not ML": fit is judged by the fit judges; young and in scope -> coverage.add_person.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from urllib.parse import urlparse

from .scope import DATA, jl, name_key

REASONS = ("moved_institution", "senior_title", "not_phd_advising_title", "postdoc_pre_independent", "clinical_unit",
           "out_of_scope_unit", "alias_of_ledger")
API_HOSTS = ("nsf.gov", "nih.gov")   # award / grant APIs: no department, so no proof of a unit


def norm(s: str) -> str:
    s = (s or "").translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}))
    return " ".join(s.lower().split())


def contains(text: str, needle: str) -> bool:
    return bool(norm(needle)) and norm(needle) in norm(text)


def api_host(url: str) -> bool:
    h = urlparse(url).netloc.lower()
    return any(h == x or h.endswith("." + x) for x in API_HOSTS)


def current_fy(today: dt.date | None = None) -> int:
    t = today or dt.date.today()
    return t.year + (1 if t.month >= 10 else 0)


def alias_target(note: str) -> str | None:
    m = re.match(r"\s*same as\s+(.+?)\s*$", note or "", re.I)
    return m.group(1) if m else None


def ledger_keys(school: str) -> set:
    return {tuple(r["key"]) for r in jl(DATA / "coverage" / "people.jsonl") if r.get("school") == school and r.get("key")}


def structural(r: dict) -> str | None:
    """Offline rules a stored row must satisfy; returns the problem or None."""
    reason, q = r.get("reason"), r.get("quote") or ""
    if reason == "alias_of_ledger":
        t = alias_target(r.get("note", ""))
        if not t:
            return 'alias_of_ledger needs --note "same as <ledger name>"'
        if name_key(t) == name_key(r.get("name", "")) or name_key(t) not in ledger_keys(r.get("school")):
            return f"'{t}' is not another person in the ledger of {r.get('school')}"
        return None
    if not q or not r.get("fetched"):
        return "no verified quote (legacy row)"
    if reason in ("clinical_unit", "out_of_scope_unit"):
        if api_host(r.get("evidence_url", "")):
            return "NSF/NIH API pages carry no department"
        if not r.get("unit") or not contains(q, r["unit"]):
            return "quote must contain the --unit name"
    elif reason == "moved_institution":
        if not r.get("to") or not contains(q, r["to"]):
            return "quote must name the new institution (--to)"
    elif reason in ("senior_title", "not_phd_advising_title"):
        if not r.get("title") or not contains(q, r["title"]):
            return "quote must contain the title (--title)"
    elif reason == "postdoc_pre_independent":
        if not r.get("fy") or r["fy"] < current_fy() - 1:
            return f"K99 fiscal year {r.get('fy')} is not active (need >= {current_fy() - 1})"
        if "reporter.nih.gov" not in r.get("evidence_url", ""):
            return "evidence must be an NIH RePORTER project"
    else:
        return f"unknown reason {reason}"
    return None


def proven(r: dict, snapshots: bool = True) -> str | None:
    """None if the row counts as a proof; else why not. With snapshots, a saved snapshot (if present) must contain the quote."""
    err = structural(r)
    if err or r.get("reason") in ("alias_of_ledger", "postdoc_pre_independent") or not snapshots:
        return err
    from outreach.fetch import SNAP, snapshot_path, visible_text
    p = snapshot_path(SNAP, r["evidence_url"])
    if p.exists() and not contains(visible_text(p.read_text(errors="ignore")), r["quote"]):
        return "quote not found on the saved snapshot"
    return None


def reporter_projects(last: str, codes: list[str]) -> list[dict]:
    from .probes import get
    out, off = [], 0
    while True:
        d = get("POST", "https://api.reporter.nih.gov/v2/projects/search",
                json={"criteria": {"pi_names": [{"last_name": last}], "activity_codes": codes}, "offset": off, "limit": 500,
                      "include_fields": ["ProjectTitle", "PrincipalInvestigators", "Organization", "FiscalYear", "ActivityCode",
                                         "ProjectNum", "ProjectDetailUrl"]}).json()
        out += d.get("results") or []
        off += 500
        if off >= (d.get("meta") or {}).get("total", 0) or not d.get("results"):
            return out


def _is_pi(proj: dict, name: str) -> bool:
    return any(name_key(f"{p.get('first_name') or ''} {p.get('last_name') or ''}") == name_key(name)
               for p in proj.get("principal_investigators") or [])


def check_k99(school: str, name: str, quote: str, reporter=reporter_projects):
    """-> (fiscal year, project url, error). Active K99 at this school, and no R00 for the same PI."""
    from .probes import org_school
    last = name_key(name)[0]
    ks = [p for p in reporter(last, ["K99"]) if _is_pi(p, name)]
    r00 = [p for p in reporter(last, ["R00"]) if _is_pi(p, name)]
    if r00:
        return None, None, f"PI has an R00 ({r00[0].get('project_num')}): already independent"
    need = current_fy() - 1
    cur = [p for p in ks if (p.get("fiscal_year") or 0) >= need and org_school((p.get("organization") or {}).get("org_name") or "") == school]
    if not cur:
        return None, None, f"no K99 for {name} at {school} with fiscal year >= {need} in RePORTER (found FY: {sorted({p.get('fiscal_year') for p in ks})})"
    best = max(cur, key=lambda p: p.get("fiscal_year") or 0)
    text = f"{best.get('project_title')} {best.get('project_num')} {(best.get('organization') or {}).get('org_name')}"
    if not contains(text, quote):
        return None, None, f"quote not in the RePORTER record ({text[:150]})"
    return best["fiscal_year"], best.get("project_detail_url"), None


def build(a, fetch=None, reporter=reporter_projects):
    """-> (row, None) or (None, refusal)."""
    r = {"school": a.school, "name": a.name, "reason": a.reason, "evidence_url": a.evidence, "note": a.note}
    for k in ("unit", "to", "title"):
        if getattr(a, k, None):
            r[k] = getattr(a, k)
    if a.reason == "alias_of_ledger":
        err = structural(r)
        return (None, err) if err else (r, None)
    if not a.quote:
        return None, "--quote is required"
    r["quote"] = a.quote
    need = {"clinical_unit": "unit", "out_of_scope_unit": "unit", "moved_institution": "to",
            "senior_title": "title", "not_phd_advising_title": "title"}.get(a.reason)
    if need and not r.get(need):
        return None, f"{a.reason} needs --{need}"
    r["fetched"] = dt.date.today().isoformat()
    if a.reason == "postdoc_pre_independent":
        fy, url, err = check_k99(a.school, a.name, a.quote, reporter)
        if err:
            return None, err
        r.update(fy=fy, evidence_url=url or a.evidence)
        err = structural(r)
        return (None, err) if err else (r, None)
    err = structural(r)
    if err:
        return None, err
    if fetch is None:
        from outreach.fetch import get as fetch
    from outreach.fetch import visible_text
    try:
        text = visible_text(fetch(a.evidence))
    except Exception as e:   # FetchError names the layer
        return None, f"could not fetch evidence: {e}"
    if not contains(text, a.quote):
        return None, f"quote not found on {a.evidence}"
    return r, None


def validate(school: str | None) -> int:
    bad = 0
    for r in jl(DATA / "coverage" / "explained.jsonl"):
        if school and school.lower() not in r.get("school", "").lower():
            continue
        err = proven(r)
        if err:
            bad += 1
            print(f"UNPROVEN {r.get('school')} | {r.get('name')} | {r.get('reason')}: {err}")
    print(f"{bad} unproven exclusion(s)")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school")
    ap.add_argument("--name")
    ap.add_argument("--reason", choices=REASONS)
    ap.add_argument("--evidence", default="", help="URL of a page you fetched that shows it")
    ap.add_argument("--quote", help="verbatim text from the evidence page (required)")
    ap.add_argument("--unit", help="clinical_unit / out_of_scope_unit: the unit name (must be in the quote)")
    ap.add_argument("--to", help="moved_institution: the new institution (must be in the quote)")
    ap.add_argument("--title", help="senior_title / not_phd_advising_title: the title (must be in the quote)")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true", help="verify, print the row, write nothing")
    ap.add_argument("--validate", action="store_true", help="re-check stored rows offline (snapshots when present)")
    a = ap.parse_args(argv)
    if a.validate:
        return validate(a.school)
    if not (a.school and a.name and a.reason):
        ap.error("--school, --name and --reason are required")
    if a.reason != "alias_of_ledger" and not a.evidence:
        ap.error("--evidence is required")
    row, err = build(a)
    if err:
        print(f"REFUSED {a.name}: {err}", file=sys.stderr)
        return 2
    if a.dry_run:
        print("OK (dry run)", json.dumps(row, ensure_ascii=False))
        return 0
    p = DATA / "coverage" / "explained.jsonl"
    rows = [x for x in jl(p) if not (x["school"] == a.school and x["name"] == a.name)] + [row]
    p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
    print(f"{a.name}: {a.reason} (verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
