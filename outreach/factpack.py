"""Fact packs for the email writer: everything an email may say about one professor, each fact tied to a source.

  python -m outreach.factpack --top 3            # highest-priority verified-earlier rows with an email
  python -m outreach.factpack --ids-file F       # one pack id per line
  -> data/email/packs/<id>.json   (people with no verifiable recent paper -> data/email/packs/_skipped.jsonl)

A paper enters a pack only if its exact title is VERBATIM on a fetched page of the professor (homepage / lab /
profile; read through outreach.fetch, so a snapshot exists) or in dblp under the professor's own author record
(affiliation matches). OpenAlex-only candidates are leads, never pack content.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Callable

from .config import ROOT, profile

DATA = ROOT / "data"
OUT = DATA / "email" / "packs"
XLSX = DATA / "export" / "advisors_v2.xlsx"
PARTICLES = {"van", "von", "de", "del", "della", "der", "den", "di", "da", "dos", "du", "la", "le", "bin", "al", "el", "ter", "ten"}
CRED = re.compile(r",?\s+(ph\.?d\.?|m\.?d\.?|sc\.?d\.?|d\.?phil|m\.?s\.?c?|m\.?eng|frs|jr\.?|sr\.?|ii|iii)\.?$", re.I)
FIT_ORDER = {"A": 0, "B": 1, "C": 2}


# ---------- small pure helpers (tested) ----------

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def surname(name: str) -> str:
    n = name
    while CRED.search(n):
        n = CRED.sub("", n).strip(" ,")
    n = re.sub(r"\([^)]*\)", " ", n)
    parts = n.split()
    if not parts:
        return ""
    i = len(parts) - 1
    while i > 0 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return " ".join(parts[i:])


def salutation(name: str) -> str:
    return f"Professor {surname(name)}"


def slug(name: str, school: str) -> str:
    base = norm(re.sub(r"\([^)]*\)", "", name)).replace(" ", "-")
    return f"{base}-{''.join(w[0] for w in norm(school).split() if w not in ('of', 'the', 'at', 'in'))}"


def title_in(title: str, text: str) -> str | None:
    """Snippet of `text` around the verbatim (case/punctuation-insensitive) title, else None."""
    t, x = norm(title), norm(text)
    if len(t) < 15 or t not in x:
        return None
    i = x.index(t)
    return x[max(0, i - 40): i + len(t) + 40]


def match_projects(texts: list[str], projects: list[dict], k: int = 2) -> list[dict]:
    """Top-k applicant projects by keyword overlap of their `matches` with the pack text (word-boundary)."""
    hay = " " + norm(" ".join(texts)) + " "
    scored = []
    for i, p in enumerate(projects):
        hits = [m for m in p.get("matches", []) if f" {norm(m)} " in hay]
        scored.append((-len(hits), i, p, hits))
    scored.sort(key=lambda t: (t[0], t[1]))
    out = [{"key": p["key"], "one_liner": " ".join(p["one_liner"].split()), "overlap": h, "weak": not h} for _, _, p, h in scored[:k]]
    return out


# ---------- sources ----------

def _page_text(url: str, fetch_page: Callable[[str], str]) -> str:
    try:
        raw = fetch_page(url)
    except Exception:
        return ""
    from .fetch import visible_text
    return visible_text(raw) if "<" in raw[:2000] else raw


def default_fetch_page(url: str) -> str:
    from .fetch import get
    return get(url)


def default_fetch_json(url: str) -> dict:
    import requests
    from .fetch import UA, ca_bundle
    time.sleep(1.2)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30, verify=ca_bundle())
    r.raise_for_status()
    return r.json()


def _hits(j: dict) -> list[dict]:
    h = (j.get("result", {}).get("hits", {}) or {}).get("hit", [])
    return h if isinstance(h, list) else [h]


def dblp_papers(name: str, institution: str, fetch_json: Callable[[str], dict], since: int) -> list[dict]:
    """Papers from dblp under the ONE author record whose affiliation note matches the institution."""
    from urllib.parse import quote
    base = re.sub(r"\([^)]*\)", "", name).strip()
    try:
        authors = _hits(fetch_json(f"https://dblp.org/search/author/api?q={quote(base)}&format=json&h=20"))
    except Exception:
        return []
    inst = [w for w in norm(institution).split() if w not in ("university", "of", "the", "at", "institute", "college")]
    good = []
    for a in authors:
        info = a.get("info", {})
        notes = info.get("notes", {}).get("note", [])
        notes = notes if isinstance(notes, list) else [notes]
        aff = norm(" ".join(n.get("text", "") for n in notes if isinstance(n, dict) and n.get("@type") == "affiliation"))
        if norm(re.sub(r"\s\d{4}$", "", info.get("author", ""))) == norm(base) and inst and all(w in aff for w in inst[:2]):
            good.append(info)
    if len(good) != 1:
        return []
    pid = good[0].get("url", "").split("/pid/")[-1]
    try:
        pubs = _hits(fetch_json(f"https://dblp.org/search/publ/api?q=author%3A{quote(pid.replace('/', ':'))}%3A&format=json&h=200"))
    except Exception:
        return []
    out = []
    for h in pubs:
        i = h.get("info", {})
        if int(i.get("year", 0) or 0) < since or i.get("type") in ("Editorship",):
            continue
        au = i.get("authors", {}).get("author", [])
        au = au if isinstance(au, list) else [au]
        names = [re.sub(r"\s\d{4}$", "", a.get("text", "")) for a in au]
        out.append({"title": i.get("title", "").rstrip("."), "year": int(i["year"]), "coauthors": [n for n in names if norm(n) != norm(base)],
                    "venue": i.get("venue", ""), "source_url": i.get("ee") or i.get("url", ""), "verified_in": "dblp"})
    return out


# ---------- ledgers ----------

def _jsonl(path: Path):
    for l in path.read_text().splitlines():
        l = l.strip()
        if l and not l.startswith('{"_'):
            try:
                yield json.loads(l)
            except ValueError:
                pass


def load_index(data: Path = DATA) -> tuple[dict, dict]:
    people, dossiers = {}, {}
    for f in sorted((data / "people").glob("*.jsonl")):
        for d in _jsonl(f):
            people[(norm(d.get("institution", "")), norm(d["name"]))] = d
    for f in sorted((data / "dossiers").glob("*.jsonl")):
        for d in _jsonl(f):
            dossiers[(norm(d.get("institution", "")), norm(d["name"]))] = d
    return people, dossiers


def load_rows(xlsx: Path = XLSX) -> list[dict]:
    import openpyxl
    ws = openpyxl.load_workbook(xlsx, read_only=True)["Advisors"]
    rows = list(ws.iter_rows(values_only=True))
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:] if r and r[2]]


def top_rows(rows: list[dict]) -> list[dict]:
    ok = [r for r in rows if r.get("evidence status") == "verified-earlier" and r.get("email")]
    return sorted(ok, key=lambda r: (r.get("priority") or 9, FIT_ORDER.get(r.get("fit"), 3)))


# ---------- build ----------

def build_pack(row: dict, people: dict, dossiers: dict, fetch_page=default_fetch_page, fetch_json=default_fetch_json,
               applicant: dict | None = None, today: date | None = None) -> tuple[dict | None, str]:
    """(pack, "") or (None, reason)."""
    applicant = applicant or profile()
    today = today or date.today()
    since = today.year - 3
    key = (norm(row["school"]), norm(row["name"]))
    person, dos = people.get(key, {}), dossiers.get(key, {})
    pid = person.get("id") or slug(row["name"], row["school"])

    cands = {}
    for src in (person.get("recent_papers") or []) + (dos.get("papers") or []):
        if src.get("title") and int(src.get("year") or 0) >= since:
            cands[norm(src["title"])] = src
    urls = [u for u in [row.get("homepage"), dos.get("lab_website") or person.get("lab_website"), dos.get("homepage"),
                        dos.get("profile_url"), dos.get("pubs")] if isinstance(u, str) and u.startswith("http")]
    urls = list(dict.fromkeys(urls))
    texts = {u: _page_text(u, fetch_page) for u in urls}

    papers = []
    for c in cands.values():
        for u, t in texts.items():
            snip = title_in(c["title"], t)
            if snip:
                papers.append({"title": c["title"], "year": int(c["year"]), "coauthors": [], "venue": "", "source_url": u,
                               "verified_in": "page", "page_snippet": snip})
                break
    if len(papers) < 3:
        for d in dblp_papers(row["name"], row["school"], fetch_json, since):
            if norm(d["title"]) not in {norm(p["title"]) for p in papers}:
                papers.append(d)
    if not papers:
        return None, "no recent paper verifiable verbatim on a fetched own/official page or dblp"
    papers.sort(key=lambda p: (-p["year"], p["verified_in"] != "page"))
    papers = papers[:3]

    res = dos.get("research") or {}
    research = {"text": res.get("text", ""), "source_url": res.get("source_url", "")} if res.get("text") else None
    if not research and person.get("keywords_evidence"):
        ke = person["keywords_evidence"]
        research = {"text": ke["quote"], "source_url": ke["source_url"]}
    rec = person.get("recruiting") or {}
    recruiting = None
    if rec.get("status") in ("Confirmed", "confirmed") and rec.get("evidence"):
        recruiting = {"status": rec["status"], "quote": rec["evidence"]["quote"], "source_url": rec["evidence"]["source_url"]}

    pack_texts = [research["text"] if research else "", " ".join(person.get("keywords") or []), row.get("theme") or "",
                  row.get("summary") or "", " ".join(p["title"] for p in papers)]
    pack = {
        "id": pid,
        "name": row["name"],
        "salutation": salutation(row["name"]),
        "surname": surname(row["name"]),
        "title": row.get("title") or (person.get("position") or {}).get("value", ""),
        "school": row["school"],
        "units": [u.strip() for u in (row.get("department(s)") or "").split(";") if u.strip()],
        "email": row["email"],
        "email_source": row.get("email source"),
        "homepage": row.get("homepage"),
        "research": research,
        "keywords": person.get("keywords") or [],
        "theme": row.get("theme"),
        "papers": papers,
        "recruiting": recruiting,
        "matched_projects": match_projects(pack_texts, applicant.get("projects", [])),
        "built_on": str(today),
    }
    return pack, ""


def write_skip(pid: str, name: str, reason: str, out: Path = OUT) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "_skipped.jsonl"
    rows = {r["id"]: r for r in _jsonl(p)} if p.exists() else {}
    rows[pid] = {"id": pid, "name": name, "reason": reason}
    p.write_text("".join(json.dumps(r) + "\n" for r in rows.values()))


def run(rows: list[dict], want: int | None, out: Path = OUT, **kw) -> list[str]:
    people, dossiers = load_index()
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for r in rows:
        if want is not None and len(made) >= want:
            break
        pack, why = build_pack(r, people, dossiers, **kw)
        if pack is None:
            pid = (people.get((norm(r["school"]), norm(r["name"]))) or {}).get("id") or slug(r["name"], r["school"])
            write_skip(pid, r["name"], why, out)
            print(f"skip {pid}: {why}")
            continue
        (out / f"{pack['id']}.json").write_text(json.dumps(pack, indent=1, ensure_ascii=False))
        made.append(pack["id"])
        print(f"pack {pack['id']}: " + " | ".join(f"{p['title']} ({p['year']}, {p['verified_in']}) {p['source_url']}" for p in pack["papers"]))
    return made


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--top", type=int)
    g.add_argument("--ids-file")
    a = ap.parse_args()
    rows = load_rows()
    people, _ = load_index()
    if a.top:
        run(top_rows(rows), a.top)
    else:
        ids = {l.strip() for l in Path(a.ids_file).read_text().splitlines() if l.strip()}
        sel = [r for r in rows if ((people.get((norm(r["school"]), norm(r["name"]))) or {}).get("id") or slug(r["name"], r["school"])) in ids]
        run(sel, None)


if __name__ == "__main__":
    main()
