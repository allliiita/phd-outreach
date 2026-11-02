"""Point census rows at the grid unit that already covers them (when the same unit exists under another name).

  python -m coverage.census_map --school "Cornell University" --from "Cornell Tech faculty" --to "Cornell Tech faculty (CS, ORIE, ECE, Info Sci at NYC)"

Rewrites grid_unit on every census row whose grid_unit == --from (or contains it as one ';' part). Refuses if --to is not a grid unit.
"""
from __future__ import annotations

import argparse
import json

from .check import split_units
from .scope import DATA, SLUG, jl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True)
    ap.add_argument("--from", dest="old", required=True)
    ap.add_argument("--to", required=True)
    a = ap.parse_args(argv)
    slug = SLUG[a.school]
    if a.to not in {g["unit"] for g in jl(DATA / "grid" / f"{slug}.jsonl")}:
        ap.error(f"--to {a.to!r} is not a unit in data/grid/{slug}.jsonl")
    p = DATA / "grid" / f"{slug}.units.jsonl"
    rows, n = jl(p), 0
    for r in rows:
        gu = r.get("grid_unit")
        if gu == a.old:
            r["grid_unit"], n = a.to, n + 1
        elif gu and a.old in split_units(gu):
            r["grid_unit"] = "; ".join(a.to if x == a.old else x for x in split_units(gu))
            n += 1
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{n} census rows remapped")
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
