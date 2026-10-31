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
import threading
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
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()
MIN_GAP = 2.0  # seconds between requests to the same host
# Hosts that refuse our self-identifying UA but serve a normal browser (no challenge): read them the way a
# person would, in Chromium with its default UA. A bot-check / challenge page is never worked around.
BROWSER_HOSTS = ROOT / "config" / "browser_hosts.txt"
CHALLENGE = re.compile(r"performing security verification|you have been blocked|access denied|verify you are human|captcha", re.I)


def browser_host(host: str) -> bool:
    if not BROWSER_HOSTS.exists():
        return False
    names = [l.strip() for l in BROWSER_HOSTS.read_text().splitlines() if l.strip() and not l.startswith("#")]
    return any(host == n or host.endswith("." + n) for n in names)


def snapshot_path(root: Path, url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    return root / urlparse(url).netloc / f"{h}.html"


def get(url: str, refresh: bool = False) -> str:
    p = snapshot_path(SNAP, url)
    if p.exists() and not refresh:
        return p.read_text(errors="ignore")
    host = urlparse(url).netloc
    if browser_host(host):
        text = render(url, browser_ua=True)
        if not text or CHALLENGE.search(visible_text(text)[:600]):
            raise RuntimeError(f"browser host served no page or a challenge (not retried): {url}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        p.with_suffix(".url").write_text(url)
        return text
    with _guard:
        lock = _locks.setdefault(host, threading.Lock())
    with lock:  # polite: one request at a time per host, MIN_GAP apart (threads fan out across hosts)
        wait = MIN_GAP - (time.time() - _last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        except requests.exceptions.SSLError:
            r = None   # incomplete certificate chain (common on university hosts); Chromium completes it
        finally:
            _last[host] = time.time()
    if r is None:
        text = render(url)
        if not text:
            raise RuntimeError(f"SSL error and browser render failed: {url}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        p.with_suffix(".url").write_text(url)
        return text
    r.raise_for_status()
    text = r.text
    if url.lower().split("?")[0].endswith(".pdf") or "pdf" in r.headers.get("content-type", ""):
        text = pdf_text(r.content)   # CVs: the snapshot holds the extracted text, so quotes stay checkable
    elif len(visible_text(text)) < 400 and "<script" in text.lower():
        text = render(url) or text   # JS-rendered homepage / directory: snapshot the rendered DOM instead
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    (p.with_suffix(".url")).write_text(url)
    return text


_pw_lock = threading.Lock()


def render(url: str, browser_ua: bool = False) -> str | None:
    """Headless Chromium (pre-installed Playwright). Serialised: one browser page at a time."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with _pw_lock, sync_playwright() as pw:
        exe = "/opt/pw-browsers/chromium"
        b = pw.chromium.launch(**({"executable_path": exe} if Path(exe).is_file() else {}))
        try:
            pg = b.new_page() if browser_ua else b.new_page(user_agent=UA)
            pg.goto(url, wait_until="networkidle", timeout=30000)
            return pg.content()
        except Exception:  # noqa: BLE001
            return None
        finally:
            b.close()


def pdf_text(data: bytes) -> str:
    import io
    from pypdf import PdfReader
    pages = PdfReader(io.BytesIO(data)).pages[:15]
    return html.escape("\n".join(pg.extract_text() or "" for pg in pages))


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
    from urllib.parse import unquote
    text = unquote(html.unescape(raw))   # mailto:%20name@x.edu
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
