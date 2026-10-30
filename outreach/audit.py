"""Audit pack: one compact file (~8k tokens) that lets an independent auditor agent look at the WHOLE
pipeline for systemic problems, without browsing or reading raw data.

  python -m outreach.audit         # -> data/audit/pack_<date>.md ; auditor follows agents/60_auditor.md

Contents: per-department funnel stats, validator problems by type, background-run logs, the top of the
shortlist (where an error costs most) and a random sample (where silent errors hide).
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from datetime import date

from .config import ROOT, profile
from .shortlist import rows as shortlist_rows

DATA = ROOT / "data"


def _jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def _rec(p: dict) -> str:
    papers = "; ".join(f"{x['title'][:70]} ({x['year']})" for x in p["recent_papers"][:2]) or "-"
    return (f"- **{p['name']}** | {p['institution']} | {'; '.join(p['departments'])[:50]} | {p['position']['value'][:45]} "
            f"| class={p['position_class']} | email={(p['email'] or {}).get('value', '-')} | fit={p.get('fit')} rel={p['relevance']}\n"
            f"  kw: {', '.join(p['keywords'][:5])}\n  papers: {papers}\n"
            f"  research: {((p.get('keywords_evidence') or {}).get('quote') or '-')[:220]}\n  notes: {p.get('notes', '')[:160]}")


def main() -> None:
    out = [f"# Audit pack {date.today()}", "",
           f"Applicant goal: {profile().get('goal', '').strip()}",
           "Scope: young faculty only (assistant / incoming / recent associate); Chinese & Asian surnames first; "
           "non-CS units first (CS deprioritised); not a census, the aim is enough well-matched advisors.", "",
           "## Funnel per unit (roster rows -> dossiers -> shortlist)",
           "| unit | roster | dossiers | email% | research% | papers% | shortlisted | fit>=4 | top problems |", "|---|---|---|---|---|---|---|---|---|"]
    short = shortlist_rows(skip_cs=True)
    by_dept = Counter(p["_stem"] for p in short if "_stem" in p)
    fit4 = Counter(p["_stem"] for p in short if (p.get("fit") or 0) >= 4 and "_stem" in p)
    for f in sorted((DATA / "dossiers").glob("*.jsonl")):
        if f.name.startswith(("csr-", "cmu-lti")):
            continue
        ds = _jl(f)
        roster = len(_jl(DATA / "roster" / f.name))
        if not ds:
            continue
        pct = lambda k: f"{100 * sum(bool(k(d)) for d in ds) // len(ds)}"
        probs = Counter(re.sub(r"[:(].*", "", p)[:30] for d in ds for p in d["problems"]).most_common(2)
        out.append(f"| {f.stem[:55]} | {roster} | {len(ds)} | {pct(lambda d: d['email'])} | {pct(lambda d: d['research']['text'])} "
                   f"| {pct(lambda d: d['papers'])} | {by_dept[f.stem]} | {fit4[f.stem]} | {'; '.join(f'{k} x{n}' for k, n in probs)} |")
    rep = (DATA / "validate_report.tsv").read_text().splitlines() if (DATA / "validate_report.tsv").exists() else []
    kinds = Counter(re.sub(r"[\w.+-]+@[\w.-]+|'[^']*'|\[[^\]]*\]|\d+", "_", l.split("\t", 1)[-1])[:70] for l in rep)
    out += ["", "## Validator problems by type", *[f"- {k}: {n}" for k, n in kinds.most_common(12)]]
    for log in ("enrich_dirs.log", "refill.log"):
        lines = (DATA / log).read_text().splitlines()[-8:] if (DATA / log).exists() else []
        out += ["", f"## Last lines of {log}", "```", *[l[-160:] for l in lines], "```"]
    out += ["", f"## Shortlist summary: {len(short)} candidates, {sum(bool(p['email']) for p in short)} with email, "
            f"heritage {dict(Counter(p.get('heritage') for p in short))}", "", "## Top 15 of the shortlist (errors here cost most)"]
    out += [_rec(p) for p in short[:15]]
    rnd = random.Random(date.today().toordinal())
    out += ["", "## Random sample of 20 shortlisted records"]
    out += [_rec(p) for p in rnd.sample(short[15:], min(20, max(0, len(short) - 15)))]
    dest = DATA / "audit"
    dest.mkdir(parents=True, exist_ok=True)
    f = dest / f"pack_{date.today()}.md"
    f.write_text("\n".join(out) + "\n")
    print(f"{f}  ~{len(f.read_text()) // 4} tokens")


if __name__ == "__main__":
    main()
