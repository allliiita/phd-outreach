"""Fit stage plumbing (no judging). Judges are agents/26_fit_tagger.md run twice on different models.

  python -m coverage.fit cards --school S [--no-fetch]   # -> data/fit/in/<slug>.jsonl
  python -m coverage.fit batches [-n 5]                  # open cards -> data/fit/batches/bNN.jsonl (mixed schools)
  python -m coverage.fit merge                           # batch judge files data/fit/out/batch-bNN.<judge>.jsonl (no --school)
  python -m coverage.fit merge --school S                # data/fit/out/<slug>.<judge>.jsonl -> decided.jsonl / tiebreak

cards: ledger people in scope, outcome open (open:title people wait for a title first), not yet decided. Research text comes
from (first non-empty) a dossier, a data/tag/in card, or the person's profile page (outreach.fetch snapshot, then
outreach.enrich.research_text). With fetching on, the card also gets `home`: the first ~800 chars of visible text after the nav
of the person's own homepage / lab page (outreach.enrich.pick_links on the profile), and up to 3 paper titles from those pages.
A card stays <= 900 chars of text (research 480 + home 240 + 3 titles x 60).
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
RESEARCH_MAX = 480
HOME_MAX = 240
PAPER_MAX = 60
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


def page_lead(raw: str, limit: int = HOME_MAX) -> str:
    """First `limit` chars of visible text after the navigation / header (menus, skip links, footers removed)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        t.decompose()
    root = soup.find("main") or soup.body or soup
    text = " ".join(root.get_text(" ").split())
    return text[:limit]


_PUB_HEAD = re.compile(r"^(selected |recent |representative |all )?(publications?|papers|preprints)\b", re.I)


def paper_titles(raw: str, limit: int = 3) -> list[str]:
    """Up to `limit` paper titles from a page: items under a Publications/Papers heading (link text, quoted title, else
    the first sentence). Heuristic and lossy by design: the judges only need a few topical hints."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, "html.parser")
    out: list[str] = []
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        if not _PUB_HEAD.match(" ".join(h.get_text(" ").split())):
            continue
        for el in h.find_all_next(["li", "p"], limit=40):
            if el.find_previous(re.compile(r"^h[1-6]$")) is not h:
                break   # next section started
            txt = " ".join(el.get_text(" ").split())
            a = el.find("a")
            at = " ".join(a.get_text(" ").split()) if a else ""
            m = re.search(r"[\"\u201c]([^\"\u201d]{15,200})[\"\u201d]", txt)
            t = m.group(1) if m else at if len(at.split()) >= 4 and not re.search(r"pdf|arxiv|code|bibtex|project", at, re.I) \
                else re.split(r"(?<=[a-z0-9\)])\.\s", txt)[0] if len(txt) > 30 else ""
            t = t.strip(" .,;")[:PAPER_MAX]
            if len(t.split()) >= 4 and t not in out:
                out.append(t)
            if len(out) >= limit:
                return out
    return out


def own_page_context(profile_url: str | None, name: str = "") -> tuple[str, list[str]]:
    """(homepage/lab lead text, paper titles) for the person's own page linked from their profile. Network via outreach.fetch
    (cached snapshots); any failure gives ('', [])."""
    if not profile_url or profile_url.startswith("mailto:"):
        return "", []
    try:
        from outreach.enrich import pick_links
        from outreach.fetch import get
        raw = get(profile_url)
        links = pick_links(raw, profile_url, name)
        lead, titles = "", []
        for u in dict.fromkeys(x for x in (links.get("homepage"), links.get("lab_website"), links.get("pubs")) if x):
            try:
                page = get(u)
            except Exception:
                continue
            if not lead and u != links.get("pubs"):
                lead = page_lead(page)
            titles += [t for t in paper_titles(page) if t not in titles]
        return lead, titles[:3]
    except Exception:
        return "", []


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
        home, titles = own_page_context(r.get("profile_url"), r["name"]) if fetch else ("", [])
        ptitles = (papers.get(k, []) + [t for t in titles if t not in papers.get(k, [])])[:3]
        cards.append({"id": cid, "name": r["name"], "school": school, "title": r.get("title") or "",
                      "units": r.get("units") or [], "research": " ".join(text.split())[:RESEARCH_MAX],
                      "home": home, "papers": [t[:PAPER_MAX] for t in ptitles], "profile_url": r.get("profile_url")})
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


def make_batches(n: int = 5) -> list[int]:
    """Open cards from data/fit/in/*.jsonl (not decided) -> data/fit/batches/b01..bNN.jsonl, round-robin so every
    batch mixes schools and sizes differ by at most 1."""
    done = decided()
    pools = []
    for f in sorted(glob.glob(str(FIT / "in" / "*.jsonl"))):
        pools.append([c for c in jl(f) if c["id"] not in done])
    cards = []
    while any(pools):   # interleave schools
        for p in pools:
            if p:
                cards.append(p.pop(0))
    out = [cards[i::n] for i in range(n)]
    for i, b in enumerate(out, 1):
        write_jsonl(FIT / "batches" / f"b{i:02d}.jsonl", b)
    return [len(b) for b in out]


def merge_batches() -> dict:
    """Judge files data/fit/out/batch-bNN.<judge>.jsonl (ids carry the school slug). Two judges agree -> decided;
    disagree (or either '?') -> decided with fit '?' and note 'judges disagree: X vs Y' (no third judge this round)."""
    cards = {}
    for f in glob.glob(str(FIT / "in" / "*.jsonl")):
        cards.update({c["id"]: c for c in jl(f)})
    got: dict[str, list] = {}
    for f in sorted(glob.glob(str(FIT / "out" / "batch-b*.*.jsonl"))):
        judge = f.rsplit("/", 1)[-1].split(".")[1]
        if judge == "tiebreak":
            continue
        for j in jl(f):
            if j.get("id") and j.get("fit") in VALID:
                got.setdefault(j["id"], []).append((judge, j))
    done = decided()
    new, waiting = [], 0
    for cid, js in got.items():
        if cid in done or cid not in cards:
            continue
        js = list({j: x for j, x in js}.items())   # one line per judge
        if len(js) < 2:
            waiting += 1
            continue
        (ja, a), (jb, b) = js[0], js[1]
        agree = a["fit"] == b["fit"] != "?"
        first = a if a["fit"] != "?" or b["fit"] == "?" else b
        row = {"id": cid, "school": cards[cid]["school"], "name": cards[cid]["name"],
               "fit": a["fit"] if agree else "?", "theme": first.get("theme", ""), "summary": first.get("summary", ""),
               "hook": first.get("hook", ""), "judges": [ja, jb]}
        if not agree:
            row["note"] = f"judges disagree: {a['fit']} vs {b['fit']}"
        new.append(row)
    if new:
        write_jsonl(FIT / "decided.jsonl", list(done.values()) + new)
    print(f"batches: decided +{len(new)} ({sum(1 for r in new if r.get('note'))} disagree), awaiting second judge {waiting}")
    return {"decided": len(new), "waiting": waiting}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cards", "merge", "batches"])
    ap.add_argument("--school")
    ap.add_argument("-n", type=int, default=5)
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "batches":
        print(make_batches(a.n))
        return
    if a.cmd == "merge" and not a.school:
        merge_batches()
        return
    if not a.school:
        ap.error("--school required")
    school = next((s for s in scope.schools() if a.school.lower() in s.lower()), a.school)
    if a.cmd == "cards":
        cmd_cards(school, not a.no_fetch)
    else:
        merge(school)


if __name__ == "__main__":
    main()
