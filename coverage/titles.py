"""Decide the young-title gate from evidence for in-scope people whose roster rows carry no title.

  python -m coverage.ledger && python -m coverage.titles --school "Cornell University" [--limit N]
  python -m coverage.ledger          # re-run: the stored titles now feed the gate

For each in-scope ledger person with an empty title: fetch the profile page (outreach.fetch.get, snapshot saved), find the
position next to the person's name (the first 'Assistant/Associate/... Professor ...' within 400 chars after the name; whole-page
first-3000-chars search, as outreach.enrich.find_title does, misses pages with long navigation), and append
{school, name, title, source_url} to data/coverage/titles.jsonl. Nothing is written when no title is found; those people stay
open and are printed (needs a human-readable look: no title on the official page).
"""
from __future__ import annotations

import argparse
import json
import re

from outreach.enrich import TITLE
from outreach.fetch import get, visible_text

from .scope import DATA, bare_name, jl


_STOP = re.compile(r"\s+(?:The|We|Our|My|His|Her|Dr|Research|Affiliations?|Publications|Program|Long|Wu|Lab)\b.*$|[.;(].*$")
_SELF = re.compile(r"(?:\bI am|\bI'm|\bis|\bjoined (?:Cornell )?as) (?:an? |the )?(?=" + TITLE.pattern.replace("(?i)", "") + ")", re.I)


def _clean(t: str) -> str:
    return _STOP.sub("", t).strip(" ,.")


def title_near_name(vis: str, name: str) -> str:
    """Professorial title right after the person's name; else 'I am / is a <title>' anywhere. Never a bare 'research scientist'."""
    parts = bare_name(name).split()
    if not parts:
        return ""
    for m in re.finditer(re.escape(parts[0]), vis):
        win = vis[m.start(): m.start() + 400]
        if parts[-1].lower() not in win[: len(name) + 40].lower():
            continue
        for t in TITLE.finditer(win):
            if re.search(r"professor", t.group(0), re.I):
                return _clean(t.group(0))
    m = _SELF.search(vis[:6000])
    if m:
        t = TITLE.match(vis, m.end())
        if t and re.search(r"professor", t.group(0), re.I):
            return _clean(t.group(0))
    return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--set", metavar="NAME", help="record a title read by hand from an official page (needs --title and --url)")
    ap.add_argument("--title")
    ap.add_argument("--url")
    a = ap.parse_args(argv)
    path = DATA / "coverage" / "titles.jsonl"
    if a.set:
        assert a.title and a.url, "--set needs --title and --url (the official page that shows it)"
        with path.open("a") as f:
            f.write(json.dumps({"school": a.school, "name": a.set, "title": a.title, "source_url": a.url}, ensure_ascii=False) + "\n")
        return 0
    done = {(t["school"], t["name"]) for t in jl(path)}
    todo = [r for r in jl(DATA / "coverage" / "people.jsonl")
            if r["school"] == a.school and r["in_scope"] and not r["title"] and (a.school, r["name"]) not in done]
    found, missing = [], []
    for r in todo[: a.limit]:
        url = r.get("profile_url")
        title = ""
        if url:
            try:
                title = title_near_name(visible_text(get(url)), r["name"])
            except Exception as e:  # noqa: BLE001
                print(f"  fetch failed {url}: {str(e)[:70]}")
        (found if title else missing).append(r["name"])
        if title:
            with path.open("a") as f:
                f.write(json.dumps({"school": a.school, "name": r["name"], "title": title, "source_url": url}, ensure_ascii=False) + "\n")
    print(f"titles found {len(found)}, none on page {len(missing)}: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
