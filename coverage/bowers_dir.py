"""Cornell Bowers college directory, one roster per department filter (CS, Information Science, Statistics & DS)

  python -m coverage.bowers_dir [--refresh]

Why a script and not config/directories/*.yaml: config/browser_hosts.txt sends bowers.cornell.edu through headless
Chromium, which is not available in the cloud container; the server answers a plain GET (200, no challenge), so this
reads it with requests and keeps the HTML under data/snapshots/ for later quote checks. cs.cornell.edu and
infosci.cornell.edu fail SSL from the cloud container; this college directory lists the same people with the
same titles and a "Field member in ..." affiliation, so it is the alternate source (status "alt") for those units.
Row shape = outreach.roster rows. The UNFILTERED directory lists only ~240 people and omits e.g. Wen Sun, Kilian Weinberger;
the department filter (?department=15|16|17&page=N) is the complete list, so that is what is read.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from outreach.fetch import SNAP, UA, snapshot_path
from outreach.roster import clean_name

URL = "https://bowers.cornell.edu/directory"
INSTITUTION = "Cornell University"
# department filter ids on the directory form (<input name=department id=edit-department-N>): unit -> (id, roster slug)
DEPTS = {"Computer Science": (15, "cornell-cs"), "Information Science": (16, "cornell-infosci"),
         "Statistics & Data Science": (17, "cornell-bowers-stat")}


def _page(dept: int, n: int, refresh: bool) -> str:
    url = f"{URL}?department={dept}&page={n}"
    p = snapshot_path(SNAP, url)
    if p.exists() and not refresh:
        return p.read_text(errors="ignore")
    time.sleep(2)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(r.text)
    p.with_suffix(".url").write_text(url)
    return r.text


def parse(html: str, url: str, unit: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select("div.directory-card"):
        name = clean_name(" ".join((card.select_one("div.name") or card).get_text(" ").split()))
        titles = [" ".join(t.get_text(" ").split()) for t in card.select("div.position-titles div.field__item")]
        aff = card.select_one("div.affiliation")
        a = card.select_one("div.email a[href^=mailto]")
        prof = card.select_one("div.view-full-profile a, a[href*='/people/']")
        main = card.select_one("div.card-content-group-main")
        row = {"name": name, "institution": INSTITUTION, "department": unit,
               "title_on_roster": "; ".join(t for t in titles if t),
               "affiliation": " ".join(aff.get_text(" ").split()) if aff else "",
               "roster_url": url, "profile_url": urljoin(URL, prof["href"]) if prof else None,
               "quote": " ".join(main.get_text(" ").split())[:300] if main else "", "filter": "all"}
        if a:
            row["block_email"] = a["href"][7:].split("?")[0].strip()
            row["block_email_quote"] = str(a)[:300]
        rows.append(row)
    return rows


def dept_rows(unit: str, refresh: bool = False) -> tuple[list[dict], int]:
    """(unique rows, cards seen) for one department, pages until a page has no cards."""
    dept = DEPTS[unit][0]
    cards, n = [], 0
    while n < 30:
        got = parse(_page(dept, n, refresh), f"{URL}?department={dept}&page={n}", unit)
        if not got:
            break
        cards += got
        n += 1
    seen, uniq = set(), []
    for r in cards:
        if r["name"] and r["name"].lower() not in seen:
            seen.add(r["name"].lower())
            uniq.append(r)
    return uniq, len(cards)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    from pathlib import Path
    for unit, (_, slug) in DEPTS.items():
        rows, cards = dept_rows(unit, ap.parse_args().refresh)
        out = Path(f"data/roster/{slug}.jsonl")
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(f"{unit}: {cards} cards, {len(rows)} unique people -> {out}")


if __name__ == "__main__":
    main()
