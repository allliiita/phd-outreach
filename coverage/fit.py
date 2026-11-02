"""Fit stage plumbing (no judging). Judges are agents/26_fit_tagger.md run twice on different models.

  python -m coverage.fit cards --school S [--no-fetch]   # -> data/fit/in/<slug>.jsonl
  python -m coverage.fit merge --school S                # data/fit/out/<slug>.<judge>.jsonl -> decided.jsonl / tiebreak

cards: ledger people in scope, outcome open, not yet decided. Research text comes from (first non-empty) a dossier,
a data/tag/in card, or the person's profile page (outreach.fetch snapshot, then outreach.enrich.research_text).
merge: two judge files agree on fit -> decided; disagree or either '?' -> data/fit/tiebreak/<slug>.jsonl for a
third judge (data/fit/out/<slug>.tiebreak.jsonl), whose answer decides ('?' stays '?').
"""
from __future__ import annotations

import argparse
import glob
import json
import re

from . import scope
from .scope import DATA, SLUG, jl

FIT = DATA / "fit"
RESEARCH_MAX = 1200
VALID = {"A", "B", "C", "?"}


def slug_of(school: str) -> str:
    return SLUG.get(school) or re.sub(r"[^a-z0-9]+", "-", school.lower()).strip("-")


def card_id(school: str, name: str) -> str:
    k = scope.name_key(name)
    return slug_of(school) + ":" + re.sub(r"[^a-z0-9]+", "-", "-".join(k).lower()).strip("-")


def decided() -> dict[str, dict]:
    return {d["id"]: d for d in jl(FIT / "decided.jsonl") if d.get("id")}


def _local_texts() -> tuple[dict, dict]:
    """(school, name_key) -> research / paper titles from existing dossiers and data/tag cards. No network."""
    res: dict[tuple, str] = {}
    papers: dict[tuple, list] = {}
    for f in sorted(glob.glob(str(DATA / "dossiers" / "*.jsonl"))):
        for d in jl(f):
            k = (scope.school_of(d.get("institution") or ""), scope.name_key(d.get("name") or ""))
            t = ((d.get("research") or {}).get("text") or "").strip()
            if t and not res.get(k):
                res[k] = t
            ps = [p["title"] for p in d.get("papers") or [] if p.get("title")]
            if ps and not papers.get(k):
                papers[k] = ps
    for f in sorted(glob.glob(str(DATA / "tag" / "in" / "*.jsonl"))):
        for d in jl(f):
            k = (scope.school_of(d.get("institution") or ""), scope.name_key(d.get("name") or ""))
            if (d.get("research") or "").strip() and not res.get(k):
                res[k] = d["research"].strip()
            ps = [p if isinstance(p, str) else p.get("title", "") for p in d.get("papers") or []]
            if [p for p in ps if p] and not papers.get(k):
                papers[k] = [p for p in ps if p]
    return res, papers


def _fetch_research(url: str | None) -> str:
    if not url or url.startswith("mailto:"):
        return ""
    try:
        from outreach.enrich import research_text
        from outreach.fetch import get
        return research_text(get(url))
    except Exception:
        return ""


def build_cards(school: str, fetch: bool = True) -> list[dict]:
    done = decided()
    res, papers = _local_texts()
    cards = []
    for r in jl(DATA / "coverage" / "people.jsonl"):
        if r["school"] != school or not r.get("in_scope") or r.get("outcome") != "open":
            continue
        g = r.get("gates") or {}
        if not all(g.get(x, True) for x in ("faculty", "young", "heritage")):
            continue
        cid = card_id(school, r["name"])
        if cid in done:
            continue
        k = (school, tuple(r["key"]))
        text = res.get(k) or (_fetch_research(r.get("profile_url")) if fetch else "")
        cards.append({"id": cid, "name": r["name"], "school": school, "title": r.get("title") or "",
                      "units": r.get("units") or [], "research": " ".join(text.split())[:RESEARCH_MAX],
                      "papers": papers.get(k, [])[:3], "profile_url": r.get("profile_url")})
    return cards


def write_jsonl(path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def cmd_cards(school: str, fetch: bool = True) -> list[dict]:
    cards = build_cards(school, fetch)
    write_jsonl(FIT / "in" / f"{slug_of(school)}.jsonl", cards)
    empty = sum(1 for c in cards if not c["research"])
    print(f"{len(cards)} cards -> data/fit/in/{slug_of(school)}.jsonl; {empty} with empty research")
    return cards


def _judgments(slug: str) -> dict[str, dict[str, dict]]:
    """judge -> id -> line, for data/fit/out/<slug>.<judge>.jsonl (judge 'tiebreak' is the third judge)."""
    out = {}
    for f in sorted(glob.glob(str(FIT / "out" / f"{slug}.*.jsonl"))):
        judge = f.rsplit("/", 1)[-1][len(slug) + 1:-len(".jsonl")]
        out[judge] = {j["id"]: j for j in jl(f) if j.get("id") and j.get("fit") in VALID}
    return out


def merge(school: str) -> dict:
    slug = slug_of(school)
    cards = {c["id"]: c for c in jl(FIT / "in" / f"{slug}.jsonl")}
    js = _judgments(slug)
    tb = js.pop("tiebreak", {})
    judges = sorted(js)
    done = decided()
    new, tie = [], []
    for cid, card in cards.items():
        if cid in done:
            continue
        got = [(j, js[j][cid]) for j in judges if cid in js[j]]
        final = None
        if len(got) >= 2 and got[0][1]["fit"] == got[1][1]["fit"] != "?":
            final, names = got[0][1], [got[0][0], got[1][0]]
        elif len(got) >= 2:
            if cid in tb:
                final, names = tb[cid], [got[0][0], got[1][0], "tiebreak"]
            else:
                tie.append({**card, "judgments": [{"judge": j, "fit": x["fit"], "theme": x.get("theme"),
                                                    "summary": x.get("summary")} for j, x in got]})
        if final:
            new.append({"id": cid, "school": school, "name": card["name"], "fit": final["fit"],
                        "theme": final.get("theme", ""), "summary": final.get("summary", ""),
                        "hook": final.get("hook", ""), "judges": names})
    if new:
        write_jsonl(FIT / "decided.jsonl", list(done.values()) + new)
    write_jsonl(FIT / "tiebreak" / f"{slug}.jsonl", tie)
    waiting = len([c for c in cards if c not in done]) - len(new) - len(tie)
    print(f"decided +{len(new)}, tiebreak {len(tie)}, awaiting judges {waiting}")
    return {"decided": len(new), "tiebreak": len(tie), "waiting": waiting}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cards", "merge"])
    ap.add_argument("--school", required=True)
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    school = next((s for s in scope.schools() if a.school.lower() in s.lower()), a.school)
    if a.cmd == "cards":
        cmd_cards(school, not a.no_fetch)
    else:
        merge(school)


if __name__ == "__main__":
    main()
