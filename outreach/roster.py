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
            name = _sel(it, cfg.get("name"))
            if not name:
                continue
            prof = _sel(it, cfg.get("profile"))
            rows.append({
                "name": name, "institution": cfg["institution"], "department": cfg["unit"],
                "title_on_roster": _sel(it, cfg.get("title")), "roster_url": url,
                "profile_url": urljoin(url, prof) if prof else None,
                "quote": " ".join(it.get_text(" ").split())[:300],
                "filter": cfg.get("filter", "all"),
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
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    if a.probe:
        return probe(a.probe)
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
