"""Cornell Bowers college directory (CS + Information Science + Statistics & Data Science) -> data/roster/cornell-bowers-directory.jsonl

  python -m coverage.bowers_dir [--refresh]

Why a script and not config/directories/*.yaml: config/browser_hosts.txt sends bowers.cornell.edu through headless
Chromium, which is not available in the cloud container; the server answers a plain GET (200, no challenge), so this
reads it with requests and keeps the HTML under data/snapshots/ for later quote checks. cs.cornell.edu and
infosci.cornell.edu fail SSL from the cloud container; this college directory lists the same people with the
same titles and a "Field member in ..." affiliation, so it is the alternate source (status "alt") for those units.
Row shape = outreach.roster rows. One row per card, per page ?page=0..N-1 (N read from the pager).
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
OUT = "data/roster/cornell-bowers-directory.jsonl"
INSTITUTION = "Cornell University"


def _page(n: int, refresh: bool) -> str:
    url = f"{URL}?page={n}"
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


def parse(html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select("div.directory-card"):
        name = clean_name(" ".join((card.select_one("div.name") or card).get_text(" ").split()))
        titles = [" ".join(t.get_text(" ").split()) for t in card.select("div.position-titles div.field__item")]
        aff = card.select_one("div.affiliation")
        a = card.select_one("div.email a[href^=mailto]")
        prof = card.select_one("div.view-full-profile a, a[href*='/people/']")
        row = {"name": name, "institution": INSTITUTION, "department": "Bowers college directory (CS, Information Science, Statistics & DS)",
               "title_on_roster": "; ".join(t for t in titles if t),
               "affiliation": " ".join(aff.get_text(" ").split()) if aff else "",
               "roster_url": url, "profile_url": urljoin(URL, prof["href"]) if prof else None,
               "quote": " ".join(card.select_one("div.card-content-group-main").get_text(" ").split())[:300]
               if card.select_one("div.card-content-group-main") else "", "filter": "all"}
        if a:
            row["block_email"] = a["href"][7:].split("?")[0].strip()
            row["block_email_quote"] = str(a)[:300]
        rows.append(row)
    return rows


def pages(refresh: bool = False) -> tuple[list[dict], int]:
    first = _page(0, refresh)
    last = max([int(m) for m in re.findall(r"\?page=(\d+)", first)] or [0])
    allrows = parse(first, f"{URL}?page=0")
    for n in range(1, last + 1):
        allrows += parse(_page(n, refresh), f"{URL}?page={n}")
    return allrows, last + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    rows, npages = pages(ap.parse_args().refresh)
    seen, uniq = set(), []
    for r in rows:
        if r["name"] and r["name"].lower() not in seen:
            seen.add(r["name"].lower())
            uniq.append(r)
    from pathlib import Path
    out = Path(OUT)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in uniq))
    print(f"{npages} pages, {len(rows)} cards, {len(uniq)} unique people -> {OUT}")


if __name__ == "__main__":
    main()
