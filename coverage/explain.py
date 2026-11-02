"""Record why a probe hit is legitimately not in the people ledger (data/coverage/explained.jsonl).

  python -m coverage.explain --school "Cornell University" --name "Yudong Chen" --reason moved_institution \
      --evidence https://pages.cs.wisc.edu/~yudongchen/ --note "Lubar Professor, UW-Madison"

Reasons (closed vocabulary; anything else is refused):
  moved_institution       now at another school (page of the new institution shows it)
  senior_title            full professor / chair / emeritus: cannot be young  (profile or roster page shows the title)
  not_phd_advising_title  teaching / research-track / lecturer / staff scientist
  postdoc_pre_independent NIH K99 (mentored phase) or similar: not yet faculty; evidence = award/project page
  clinical_unit           clinical department / hospital-only appointment (Weill clinical, business, public health)
  out_of_scope_unit       faculty in a unit the targets do not cover (physics, chemistry, wet-lab-only unit): name the unit
  alias_of_ledger         the probe uses another spelling of someone who IS in the ledger: --note "same as <ledger name>"
Evidence must be a page you fetched (official page, or the award page that shows the fact). Never explain a person away with
"not ML": fit is judged by the fit judges; if a person is young and in scope add them with coverage.add_person.
"""
from __future__ import annotations

import argparse
import json

from .scope import DATA, jl

REASONS = ("moved_institution", "senior_title", "not_phd_advising_title", "postdoc_pre_independent", "clinical_unit",
           "out_of_scope_unit", "alias_of_ledger")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--reason", required=True, choices=REASONS)
    ap.add_argument("--evidence", required=True, help="URL of a page you fetched that shows it")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    p = DATA / "coverage" / "explained.jsonl"
    rows = [r for r in jl(p) if not (r["school"] == a.school and r["name"] == a.name)]
    rows.append({"school": a.school, "name": a.name, "reason": a.reason, "evidence_url": a.evidence, "note": a.note})
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{a.name}: {a.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
