"""Deterministic rostering. An agent writes a small YAML of CSS selectors once per directory
(config/directories/<slug>.yaml); this code runs it, so names/titles/URLs are never typed by an LLM.

  python -m outreach.roster config/directories/cmu-stat.yaml      # -> data/roster/cmu-stat.jsonl
  python -m outreach.roster --all                                  # every YAML
  python -m outreach.roster --probe URL                            # repeated blocks, to help write a YAML

YAML keys: institution, unit, urls (list; paginated pages), item (CSS selector of one person block),
name / title / profile (CSS selector inside the block; `sel@attr` reads an attribute), expect (row count),
filter: all | ml_only, skip_titles: [regex, ...] (optional).
Selector `.` means the item itself.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup

from .config import ROOT
from .fetch import get

DIRS = ROOT / "config" / "directories"
OUT = ROOT / "data" / "roster"


def _sel(node, spec: str | None) -> str:
    if not spec:
        return ""
    css, _, attr = spec.partition("@")
    el = node if css in (".", "") else node.select_one(css)
    if el is None:
        return ""
    return (el.get(attr) or "") if attr else " ".join(el.get_text(" ").split())


def run(cfg_path: Path, refresh: bool = False) -> tuple[list[dict], list[str]]:
    cfg = yaml.safe_load(cfg_path.read_text())
    rows, problems = [], []
    for url in cfg["urls"]:
        soup = BeautifulSoup(get(url, refresh), "html.parser")
        items = soup.select(cfg["item"])
        if not items:
            problems.append(f"{url}: selector {cfg['item']!r} matched nothing (page changed or JS-rendered)")
        for it in items:
            name = clean_name(_sel(it, cfg.get("name")))
            if not name:
                continue
            prof = _sel(it, cfg.get("profile"))
            rows.append({
                "name": name, "institution": cfg["institution"], "department": cfg["unit"],
                "title_on_roster": _sel(it, cfg.get("title")), "roster_url": url,
                "profile_url": urljoin(url, prof) if prof else None,
                "quote": " ".join(it.get_text(" ").split())[:300],
                "filter": cfg.get("filter", "all"), **_mailto(it),
            })
    skip = [re.compile(p, re.I) for p in cfg.get("skip_titles", [])]
    rows = [r for r in rows if not any(p.search(r["title_on_roster"]) for p in skip)]
    seen, uniq = set(), []
    for r in rows:
        if r["name"].lower() not in seen:
            seen.add(r["name"].lower())
            uniq.append(r)
    exp = cfg.get("expect")
    if exp and abs(len(uniq) - exp) > max(2, exp * 0.1):
        problems.append(f"count {len(uniq)} vs expected {exp}: re-check selectors / pagination")
    if uniq and sum(not r["title_on_roster"] for r in uniq) > len(uniq) / 2:
        problems.append("most rows have no title: check the title selector")
    return uniq, problems


TITLE_WORD = re.compile(r"\b(professor|lecturer|instructor|scientist|faculty|chair|emerit\w*)\b", re.I)
NAME_RE = re.compile(r"^[A-Z][\w'’.\-]+(?: [A-Z][\w'’.\-]*){1,3}$")
LAST_FIRST = re.compile(r"^([A-Z][\w'’\-]+(?: [A-Z][\w'’\-]+)?), ([A-Z][\w'’.\-]+(?: [A-Z][\w'’.\-]*)?)$")
NOT_NAME = re.compile(r"\b(read|more|bio|profile|website|email|contact|faculty|people|department|research|news|view|"
                      r"statistics|science|university|school|center|institute|program|home)\b", re.I)


NOT_FACULTY = re.compile(r"year enrolled|ph\.?d\.? (student|candidate)|graduate student|doctoral (student|candidate)|"
                         r"\bstudent\b|postdoc|post-doctoral|\bstaff\b|administrat|coordinator|assistant to|alumn", re.I)


def faculty_like(r: dict) -> bool:
    """Directories often list students and staff too; drop them before any page is opened."""
    if re.search(r"\b(lab|laboratory|group|center|centre|program|institute|core)\b", r.get("name") or "", re.I):
        return False   # "Cohen Lab" is not a person (audit 2026-10-30)
    if TITLE_WORD.search(r.get("title_on_roster") or ""):
        return not NOT_FACULTY.search(r["title_on_roster"])
    return not NOT_FACULTY.search(r.get("quote") or "")


def _mailto(el) -> dict:
    """Address linked inside this person's own block (often a UNI like aa4481@...), with the tag as quote."""
    a = el.find("a", href=re.compile(r"^mailto:", re.I)) if hasattr(el, "find") else None
    if not a:
        return {}
    addr = a["href"][7:].split("?")[0].strip()
    quote = str(a)[:300]
    return {"block_email": addr, "block_email_quote": quote} if "@" in addr else {}


def _sig(el) -> str:
    return el.name + ("." + el["class"][0] if el.get("class") else "")


DEGREE = re.compile(r"^(?:(?:dr|prof|professor|phd|ph\.d\.|scd|md|mph|drph)\.?,?\s+)+|(?:,\s*(?:phd|ph\.d\.|scd|md|mph|ms|ma|drph)\.?)+$", re.I)   # suffix degrees only after a comma: "Ying Ma" stays
DEGREE_CAPS = re.compile(r"(?:,?\s+(?:PhD|Ph\.D\.|ScD|MD|MPH|DrPH|MBBS|FACMI|MS|MA|MSc|MSHP|MSCE|MBA|MPhil|RN|PharmD|[A-Z]{2,6}))+$")   # trailing all-caps credentials   # "Jane Doe MD" (case-sensitive)


def clean_name(t: str) -> str:
    return DEGREE_CAPS.sub("", DEGREE.sub("", t)).strip(" ,")


def _name_in(el):
    """(name, link) from the first heading / strong / link whose text is shaped like a person's name."""
    for h in ([el] if el.name == "a" else []) + el.find_all(["h2", "h3", "h4", "h5", "strong", "a", "span"]):
        t = clean_name(" ".join(h.get_text(" ").split()).strip(" ,"))
        m = LAST_FIRST.match(t)
        if m:
            t = f"{m.group(2)} {m.group(1)}"
        if NAME_RE.match(t) and not TITLE_WORD.search(t) and not NOT_NAME.search(t):
            a = h if h.name == "a" else (h.find("a", href=True) or h.find_parent("a"))
            return t, (a.get("href") if a else None)
    return "", None


def _next_page(soup, url: str) -> str | None:
    a = soup.find("a", rel="next") or soup.select_one(".pager__item--next a, li.next a, a.next") or soup.find("a", string=re.compile(r"^\s*(next|›|»|next ›|next page)\s*$", re.I))
    return urljoin(url, a["href"]) if a and a.get("href") else None


def auto(url: str, institution: str, unit: str, refresh: bool = False) -> tuple[list[dict], str]:
    """No selectors: pick the repeated block type whose blocks mostly hold a person-shaped name (titles are a
    bonus), read name / title / profile link from each, follow `next` pagination (<= 15 pages)."""
    from .fetch import get as fetch
    rows, how, page, seen_pages = [], "", url, set()
    while page and page not in seen_pages and len(seen_pages) < 15:
        seen_pages.add(page)
        soup = BeautifulSoup(fetch(page, refresh), "html.parser")
        nxt = _next_page(soup, page)
        for t in soup(["nav", "header", "footer"]):
            t.decompose()
        groups: dict[str, list] = {}
        for el in soup.find_all(True):
            if el.name in ("html", "body", "main", "ul", "ol", "table", "tbody", "section", "form"):
                continue
            txt = el.get_text(" ", strip=True)
            if 5 < len(txt) < 700 and (el.name == "a" or el.find("a", href=True)):
                groups.setdefault(_sig(el), []).append(el)
        best, best_score = None, 0.0
        for sig, els in groups.items():
            named = sum(bool(_name_in(e)[0]) for e in els)
            titled = sum(bool(TITLE_WORD.search(e.get_text(" "))) for e in els)
            score = named * (1.5 if titled >= named / 2 else 1.0) - 0.01 * len(els)
            if len(els) >= 4 and named / len(els) >= 0.6 and score > best_score:
                best, best_score = sig, score
        if not best:
            break
        how = f"auto: {best}, {len(seen_pages)} page(s)"
        for el in groups[best]:
            name, prof = _name_in(el)
            if not name:
                continue
            if not prof or prof.startswith("mailto:"):
                a = next((x for x in ([el] if el.name == "a" else []) + el.find_all("a", href=True)
                          if not x.get("href", "").startswith("mailto:")), None)
                prof = a.get("href") if a else None
            lines = [l.strip() for l in el.get_text("\n").split("\n") if l.strip()]
            title = next((l for l in lines if TITLE_WORD.search(l) and len(l) < 150), "")
            rows.append({"name": name, "institution": institution, "department": unit, "title_on_roster": title,
                         "roster_url": page, "profile_url": urljoin(page, prof) if prof else None,
                         "quote": " ".join(el.get_text(" ").split())[:300], "filter": "all", **_mailto(el)})
        page = nxt
    if not rows:
        return [], "no repeated person blocks found (JS directory? write a YAML or use the browser)"
    dropped = sum(not faculty_like(r) for r in rows)
    rows = [r for r in rows if faculty_like(r)]
    how += f", dropped {dropped} students/staff" if dropped else ""
    seen, uniq = set(), []
    for r in rows:
        if r["name"].lower() not in seen:
            seen.add(r["name"].lower())
            uniq.append(r)
    return uniq, how


def probe(url: str) -> None:
    """Print the most repeated element signatures that contain a link, to help write `item`."""
    soup = BeautifulSoup(get(url), "html.parser")
    sig = Counter()
    for el in soup.find_all(True):
        if el.find("a", href=True) and 15 < len(el.get_text(" ", strip=True)) < 400:
            sig[f"{el.name}.{'.'.join(el.get('class', []))}"] += 1
    for s, n in sig.most_common(12):
        css = s.rstrip(".")
        ex = soup.select_one(css) if "." in css else None
        print(f"{n:4d}  {css:50s}  {(ex.get_text(' ', strip=True)[:90] if ex else '')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cfg", nargs="?", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--probe")
    ap.add_argument("--departments", type=Path, help="data/departments.jsonl: run auto mode on every line")
    ap.add_argument("--auto", nargs=4, metavar=("URL", "INSTITUTION", "UNIT", "SLUG"),
                    help="no-selector mode; writes data/roster/SLUG.jsonl")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    if a.probe:
        return probe(a.probe)
    if a.departments:
        OUT.mkdir(parents=True, exist_ok=True)
        for l in a.departments.read_text().splitlines():
            if not l.strip():
                continue
            d = json.loads(l)
            slug = d.get("slug") or re.sub(r"[^a-z0-9]+", "-", f"{d['institution']} {d['unit']}".lower()).strip("-")
            if (DIRS / f"{slug}.yaml").exists() or ((OUT / f"{slug}.jsonl").exists() and not a.refresh):
                continue
            try:
                rows, how = auto(d["url"], d["institution"], d["unit"], refresh=a.refresh)
                if not rows:   # JS-built list: snapshot the rendered DOM and try once more
                    from .fetch import SNAP, render, snapshot_path
                    html = render(d["url"])
                    if html:
                        snapshot_path(SNAP, d["url"]).write_text(html)
                        rows, how = auto(d["url"], d["institution"], d["unit"])
                        how += " (rendered)"
            except Exception as e:  # noqa: BLE001
                rows, how = [], f"FAILED {type(e).__name__} {str(e)[:80]}"
            for r in rows:
                r["filter"] = d.get("filter", "all")
            if rows:
                (OUT / f"{slug}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            print(f"{slug}: {len(rows)} rows ({how})" if rows else f"{slug}: NEEDS YAML/MANUAL ({how}) {d['url']}")
        return
    if a.auto:
        rows, how = auto(*a.auto[:3], refresh=a.refresh)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{a.auto[3]}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        print(f"{a.auto[3]}: {len(rows)} rows ({how}); titles: {Counter(r['title_on_roster'][:30] for r in rows).most_common(4)}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    bad = 0
    for cfg in (sorted(DIRS.glob("*.yaml")) if a.all else [a.cfg]):
        rows, probs = run(cfg, a.refresh)
        (OUT / f"{cfg.stem}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        print(f"{cfg.stem}: {len(rows)} rows" + (f"  PROBLEMS: {'; '.join(probs)}" if probs else ""))
        bad += bool(probs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
