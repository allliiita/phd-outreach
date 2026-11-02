"""What is missing, per school? One command, no LLM. Used to resume interrupted work and to prove a batch is complete.

  python -m outreach.progress            # all focus schools
  python -m outreach.progress uw ucsd    # some schools (by slug)

Checks, in pipeline order: unit census file -> grid lines and their status -> every roster file is registered in the grid
(orphans) -> every done grid line has a roster whose row count equals `rows` -> verifier verdicts -> young Chinese-surname
candidates enriched (dossier exists) -> tagged -> A/B/? read by a dossier worker.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

from .batch1 import SLUG, jl, keep, targets
from .config import ROOT

DATA = ROOT / "data"


def school(inst: str, slug: str) -> list[str]:
    todo = []
    if not (DATA / "grid" / f"{slug}.units.jsonl").exists():
        todo.append("unit census missing (agents/07_unit_census.md)")
    grid = jl(DATA / "grid" / f"{slug}.jsonl")
    if not grid:
        todo.append("grid missing")
    registered = {Path(g["roster"]).name for g in grid if g.get("roster")}
    for f in sorted(glob.glob(str(DATA / "roster" / f"{slug}-*.jsonl"))):
        if Path(f).name not in registered:
            todo.append(f"orphan roster (not in grid): {Path(f).name}")
    for g in grid:
        st, r = g.get("status"), g.get("roster")
        if st in ("todo", None):
            todo.append(f"unit not rostered: {g.get('unit')}")
        elif st in ("done", "partial"):
            rows = [x for x in jl(ROOT / r) if "name" in x] if r else []
            if not rows:
                todo.append(f"done but roster empty/missing: {g.get('unit')}")
            elif g.get("rows") not in (None, len(rows)):
                todo.append(f"row mismatch {g.get('unit')}: grid {g.get('rows')} vs file {len(rows)}")
    if grid and not (DATA / "grid" / f"{slug}.verdicts.jsonl").exists():
        todo.append("no verifier verdicts (agents/15_roster_verifier.md)")
    people = {(p["name"].lower().strip(), p["institution"]): p for p in jl(DATA / "tag" / "people.jsonl")}
    tagged = {t["id"] for f in glob.glob(str(DATA / "tag" / "out" / "*.jsonl")) for t in jl(Path(f))}
    fits = {}
    for f in sorted(glob.glob(str(DATA / "tag" / "out" / "*.jsonl"))) + sorted(glob.glob(str(DATA / "tag" / "re_out" / "*.jsonl"))):
        for t in jl(Path(f)):
            fits[t["id"]] = t.get("fit")
    dossiers = {d["id"] for f in glob.glob(str(DATA / "dossier_out" / "*.jsonl")) for d in jl(Path(f))}
    n_cand = n_enr = 0
    for g in grid:
        r = g.get("roster")
        if not r or g.get("status") not in ("done", "partial"):
            continue
        cands = [x for x in jl(ROOT / r) if "name" in x and keep(x)]
        n_cand += len(cands)
        if cands and not (DATA / "dossiers" / Path(r).name).exists():
            todo.append(f"not enriched: {Path(r).name} ({len(cands)} candidates)")
        n_enr += len(cands)
    mine = [p for k, p in people.items() if k[1] == inst]
    untagged = [p for p in mine if p["id"] not in tagged]
    if untagged:
        todo.append(f"{len(untagged)} people not tagged (python -m outreach.batch1 cards)")
    unread = [p for p in mine if fits.get(p["id"]) in ("A", "B", "?") and p["id"] not in dossiers]
    if unread:
        todo.append(f"{len(unread)} A/B/? people without a dossier (agents/21_dossier_worker.md)")
    return [f"candidates in rosters: {n_cand}; people: {len(mine)}"] + (todo or ["COMPLETE"])


def main() -> None:
    want = set(sys.argv[1:])
    for inst in targets()["focus_schools"]:
        slug = SLUG.get(inst)
        if not slug or (want and slug not in want):
            continue
        res = school(inst, slug)
        print(f"== {inst} ({slug})")
        for line in res:
            print("   ", line)


if __name__ == "__main__":
    main()
