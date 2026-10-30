"""Recent papers from structured sources (titles/years are never typed by an LLM).

  python -m outreach.papers "Firstname Lastname" "Carnegie Mellon University" [--page URL ...]

Providers: OpenAlex when OPENALEX_API_KEY is set (env or secrets/openalex_key; free key), else Semantic
Scholar. Author disambiguation is deterministic: a candidate is accepted when its paper titles appear in the
person's own profile/homepage text, or (OpenAlex) its affiliation matches the institution. Otherwise the
result is {"problem": "ambiguous ..."} and papers stay empty: never pick a same-name author blindly.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from datetime import date

import requests

from .config import ROOT

S2 = "https://api.semanticscholar.org/graph/v1"
OA = "https://api.openalex.org"
N_KEEP = 8                  # titles kept for the judge; the record uses 1-3 of them
_lock, _last = threading.Lock(), [0.0]


def _key() -> str | None:
    k = os.environ.get("OPENALEX_API_KEY")
    f = ROOT / "secrets" / "openalex_key"
    return k or (f.read_text().strip() if f.exists() else None)


def _get(url: str, params: dict, gap: float = 1.1) -> dict:
    for attempt in range(8):
        with _lock:
            w = gap - (time.time() - _last[0])
            if w > 0:
                time.sleep(w)
            r = requests.get(url, params=params, timeout=30,
                             headers={"x-api-key": os.environ["S2_API_KEY"]} if "semanticscholar" in url and os.environ.get("S2_API_KEY") else {})
            _last[0] = time.time()
        if r.status_code in (429, 503):
            time.sleep(min(60, 2 ** attempt * 2))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"rate limited: {url}")


def _norm(t: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())


def _on_page(titles: list[str], page: str) -> int:
    p = _norm(page)
    return sum(1 for t in titles if len(_norm(t)) > 25 and _norm(t)[:60] in p)


def _pick(works: list[dict]) -> list[dict]:
    since = date.today().year - 3
    seen, out = set(), []
    for w in sorted(works, key=lambda w: (-(w["year"] or 0), -(w.get("cites") or 0))):
        k = _norm(w["title"])[:80]
        if not w["year"] or w["year"] < since or k in seen or len(k) < 10:
            continue
        seen.add(k)
        out.append({"title": w["title"], "year": w["year"], "url": w["url"], "source": w["source"]})
        if len(out) == N_KEEP:
            break
    return out


def _s2(name: str, institution: str, page: str) -> dict:
    found = _get(f"{S2}/author/search", {"query": name, "limit": 10,
                                         "fields": "name,affiliations,homepage,paperCount,papers.title,papers.year"})
    inst = {t for t in institution.lower().split() if len(t) > 3}
    good = []
    for a in found.get("data", []):
        titles = [p["title"] for p in a.get("papers", []) if p.get("title")]
        hits = _on_page(titles, page)
        aff = any(inst & set(x.lower().split()) for x in a.get("affiliations") or [])
        if hits or aff:
            good.append((hits, a))
    if not good:
        n = len(found.get("data", []))
        return {"problem": f"papers: {n} same-name S2 authors, none confirmed by page text" if n else "papers: no S2 author"}
    if any(h for h, _ in good):   # page-confirmed ids only; an affiliation-only id can be a same-name colleague
        good = [(h, a) for h, a in good if h]
    elif len(good) > 1:
        return {"problem": f"papers: {len(good)} S2 authors match the affiliation, none confirmed by page text"}
    works = []
    for _, a in good:   # S2 often splits one person into several ids; merge every confirmed id
        res = _get(f"{S2}/author/{a['authorId']}/papers", {"fields": "title,year,externalIds,citationCount,url", "limit": 100})
        for p in res.get("data", []):
            ext = p.get("externalIds") or {}
            url = (f"https://doi.org/{ext['DOI']}" if ext.get("DOI") else
                   f"https://arxiv.org/abs/{ext['ArXiv']}" if ext.get("ArXiv") else p.get("url"))
            if p.get("title") and url:
                works.append({"title": p["title"], "year": p.get("year"), "url": url, "cites": p.get("citationCount"), "source": "semantic_scholar"})
    return {"author": [a["authorId"] for _, a in good], "papers": _pick(works)}


_inst_ids: dict[str, str | None] = {}


def _inst_id(institution: str, key: str) -> str | None:
    if institution not in _inst_ids:
        from .config import institutions
        alias = next((i.get("openalex") for i in institutions()["institutions"] if i["name"] == institution), None)
        res = _get(f"{OA}/institutions", {"search": alias or institution, "per-page": 1, "api_key": key}, gap=0.4)["results"]
        _inst_ids[institution] = res[0]["id"].split("/")[-1] if res else None
    return _inst_ids[institution]


def _openalex(name: str, institution: str, page: str, key: str) -> dict:
    """Authors with this name affiliated with this institution (by OpenAlex id, not by words), and only their
    works that carry this institution: a same-name author elsewhere cannot leak in."""
    iid = _inst_id(institution, key)
    if not iid:
        return {"problem": f"papers: OpenAlex has no institution {institution!r}"}
    auth = {"api_key": key}
    found = _get(f"{OA}/authors", {"search": name, "filter": f"affiliations.institution.id:{iid}", "per-page": 10, **auth}, gap=0.4)["results"]
    if not found:
        return {"problem": "papers: no OpenAlex author with this name at this institution"}
    since = date.today().year - 3
    words = set(_norm(page).split())
    per = []
    for a in found[:5]:   # OpenAlex splits people too; score each same-name candidate separately
        aid = a["id"].split("/")[-1]
        res = _get(f"{OA}/works", {"filter": f"author.id:{aid},institutions.id:{iid},from_publication_date:{since}-01-01,type:article|preprint",
                                   "select": "title,publication_year,doi,primary_location,cited_by_count,authorships,id",
                                   "sort": "publication_date:desc", "per-page": 40, **auth}, gap=0.4)
        works = [{"title": w["title"], "year": w["publication_year"], "cites": w.get("cited_by_count"),
                  "url": w.get("doi") or (w.get("primary_location") or {}).get("landing_page_url") or w["id"],
                  "source": "openalex"} for w in res["results"]
                 if w.get("title") and len(w.get("authorships") or []) <= 30]   # drop big-collaboration papers
        if works:
            vocab = set(_norm(" ".join(w["title"] for w in works)).split())
            per.append((_on_page([w["title"] for w in works], page), len(words & vocab) / (len(vocab) ** 0.5 + 1), aid, works))
    if not per:
        return {"problem": "papers: OpenAlex author found but no recent works at this institution"}
    hit = [x for x in per if x[0]]
    if hit:
        chosen, note = hit, None
    else:
        per.sort(key=lambda x: -x[1])
        chosen = per[:1]
        note = None if len(per) == 1 else f"papers: {len(per)} same-name OpenAlex authors at this school; picked closest to page text, check"
    works = [w for x in chosen for w in x[3]]
    out = {"author": "|".join(x[2] for x in chosen), "papers": _pick(works)}
    first = _get(f"{OA}/works", {"filter": f"author.id:{out['author']}", "sort": "publication_year:asc", "per-page": 1,
                                 "select": "publication_year", **auth}, gap=0.4)["results"]
    out["first_year"] = first[0]["publication_year"] if first else None   # career-age proxy for "young"
    if note:
        out["warning"] = note
    return out


def find_papers(name: str, institution: str, page_text: str = "", scholar: str | None = None) -> dict:
    try:
        key = _key()
        if key:
            res = _openalex(name, institution, page_text, key)
            if not res.get("problem"):
                return res
            s2 = _s2(name, institution, page_text)   # new arrivals: works may not carry the institution yet
            return s2 if not s2.get("problem") else res
        return _s2(name, institution, page_text)
    except Exception as e:  # noqa: BLE001
        return {"problem": f"papers: {type(e).__name__} {str(e)[:100]}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("institution")
    ap.add_argument("--page", nargs="*", default=[], help="profile/homepage URLs whose text confirms the author")
    a = ap.parse_args()
    from .fetch import get, visible_text
    res = find_papers(a.name, a.institution, " ".join(visible_text(get(u)) for u in a.page))
    print(json.dumps(res, indent=1, ensure_ascii=False))
    sys.exit(2 if res.get("problem") else 0)


if __name__ == "__main__":
    main()
