"""Deterministic fetching with saved snapshots. Agents read pages through this so every quote and
email can later be checked against the exact bytes that were fetched.

  python -m outreach.fetch URL            -> prints visible text, saves snapshot
  python -m outreach.fetch URL --emails   -> prints emails found in the raw HTML (incl. obfuscated, mailto:)
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import ROOT
from .schema import deobfuscate

SNAP = ROOT / "data" / "snapshots"
UA = "Mozilla/5.0 (academic-directory-research; contact via applicant email)"
_last: dict[str, float] = {}
MIN_GAP = 2.0  # seconds between requests to the same host


def snapshot_path(root: Path, url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    return root / urlparse(url).netloc / f"{h}.html"


def get(url: str, refresh: bool = False) -> str:
    p = snapshot_path(SNAP, url)
    if p.exists() and not refresh:
        return p.read_text(errors="ignore")
    host = urlparse(url).netloc
    wait = MIN_GAP - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    _last[host] = time.time()
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(r.text)
    (p.with_suffix(".url")).write_text(url)
    return r.text


def visible_text(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return " ".join(soup.get_text(" ").split())


def links(raw: str, base: str) -> list[tuple[str, str]]:
    from urllib.parse import urljoin
    soup = BeautifulSoup(raw, "html.parser")
    return [(" ".join(a.get_text(" ").split()), urljoin(base, a["href"])) for a in soup.find_all("a", href=True)]


EMAIL_PAT = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")


def emails(raw: str) -> list[tuple[str, str]]:
    """(email, 80-char context) pairs from mailto links, plain text and [at]/[dot] obfuscation.
    Cloudflare-protected addresses (data-cfemail) are decoded too."""
    found: dict[str, str] = {}
    text = html.unescape(raw)
    for m in re.finditer(r'data-cfemail="([0-9a-f]+)"', raw):
        enc = bytes.fromhex(m.group(1))
        found.setdefault("".join(chr(b ^ enc[0]) for b in enc[1:]).lower(), "cloudflare-protected")
    vis = visible_text(raw)
    for src in (text, vis, deobfuscate(vis)):
        for m in EMAIL_PAT.finditer(src):
            e = m.group(0).strip(".").lower()
            if e.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
                continue
            found.setdefault(e, src[max(0, m.start() - 40): m.end() + 40])
    return sorted(found.items())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--emails", action="store_true")
    ap.add_argument("--links", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    raw = get(a.url, a.refresh)
    if a.emails:
        for e, ctx in emails(raw):
            print(f"{e}\t{ctx}")
    elif a.links:
        for t, u in links(raw, a.url):
            print(f"{t}\t{u}")
    else:
        print(visible_text(raw))


if __name__ == "__main__":
    main()
