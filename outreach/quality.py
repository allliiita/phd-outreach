"""Data-quality gates applied at assemble time (from audit 2026-10-30). Blank beats wrong.

- research text that is page junk (menus, course blurbs, mid-word fragments) is dropped
- papers are dropped when the author match was uncertain (same-name warnings) or when no paper shares a
  content word with the person's own research text (likely another person's papers)
- keyword fragments are trimmed of dangling stopwords
"""
from __future__ import annotations

import re

MENU = re.compile(r"\b(overview|admissions?|directory|contact|independent study|resources|mailing address|"
                  r"organizations|community|newsletter|apply|give|events|news|careers|menu|search)\b", re.I)
STOP = set("a an the of in on for to and or with by from at as is are be this that their our its into via using".split())


def research_ok(t: str) -> bool:
    t = t.strip()
    if len(t) < 80:
        return False
    if t[0].islower() or not re.match(r"[A-Z0-9\"“(]", t):   # starts mid-word / mid-sentence
        return False
    return len(MENU.findall(t)) < 2


def _words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{5,}", t.lower()) if w not in STOP}


def papers_ok(d: dict) -> tuple[bool, str]:
    if not d["papers"]:
        return True, ""
    if any("same-name" in p or "different person" in p for p in d["problems"]):
        return False, "papers dropped: same-name author not confirmed"
    rt = d["research"]["text"]
    if rt and research_ok(rt):
        rw = _words(rt)
        if rw and not any(_words(p["title"]) & rw for p in d["papers"]):
            return False, "papers dropped: no overlap with own research text"
    return True, ""


def trim_kw(k: str) -> str:
    ws = k.split()
    while ws and ws[0].lower() in STOP:
        ws = ws[1:]
    while ws and ws[-1].lower() in STOP:
        ws = ws[:-1]
    return " ".join(ws)


def apply(d: dict) -> dict:
    """Return a cleaned copy of a dossier (the stored dossier is left untouched)."""
    d = {**d, "problems": list(d["problems"])}
    if d["research"]["text"] and not research_ok(d["research"]["text"]):
        d["research"] = {"text": "", "source_url": None}
        d["problems"].append("research text dropped: page junk")
    ok, why = papers_ok(d)
    if not ok:
        d["papers"] = []
        d["problems"].append(why)
    return d
