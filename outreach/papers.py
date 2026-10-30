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
    for attempt in range(5):
        with _lock:
            w = gap - (time.time() - _last[0])
            if w > 0:
                time.sleep(w)
            r = requests.get(url, params=params, timeout=30,
                             headers={"x-api-key": os.environ["S2_API_KEY"]} if "semanticscholar" in url and os.environ.get("S2_API_KEY") else {})
            _last[0] = time.time()
        if r.status_code == 429:
            time.sleep(2 ** attempt * 2)
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


def _openalex(name: str, institution: str, page: str, key: str) -> dict:
    auth = {"api_key": key}
    found = _get(f"{OA}/authors", {"search": name, "per-page": 15, **auth}, gap=0.2)
    inst = {t for t in institution.lower().replace(",", " ").split() if len(t) > 3}
    scored = []
    for a in found["results"]:
        insts = [i.get("display_name", "") for i in (a.get("last_known_institutions") or [])]
        insts += [x["institution"]["display_name"] for x in a.get("affiliations", [])[:5]]
        s = max((len(inst & set(i.lower().split())) for i in insts), default=0)
        if s:
            scored.append((s, a))
    scored.sort(key=lambda x: -x[0])
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0] and not page):
        return {"problem": f"papers: OpenAlex ambiguous ({len(scored)} candidates)"}
    since = date.today().year - 3
    picked = []
    for _, a in scored[:3]:
        aid = a["id"].split("/")[-1]
        res = _get(f"{OA}/works", {"filter": f"author.id:{aid},from_publication_date:{since}-01-01",
                                   "sort": "publication_date:desc", "per-page": 50, **auth}, gap=0.2)
        works = [{"title": w["title"], "year": w["publication_year"], "cites": w.get("cited_by_count"),
                  "url": w.get("doi") or (w.get("primary_location") or {}).get("landing_page_url") or w["id"],
                  "source": "openalex"} for w in res["results"] if w.get("title")]
        picked.append((_on_page([w["title"] for w in works], page), a["id"], works))
        if not page:
            break
    picked.sort(key=lambda x: -x[0])
    if page and len(picked) > 1 and picked[0][0] == 0:
        return {"problem": "papers: OpenAlex candidates not confirmed by page text"}
    return {"author": picked[0][1], "papers": _pick(picked[0][2])}


def find_papers(name: str, institution: str, page_text: str = "", scholar: str | None = None) -> dict:
    try:
        key = _key()
        return _openalex(name, institution, page_text, key) if key else _s2(name, institution, page_text)
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
