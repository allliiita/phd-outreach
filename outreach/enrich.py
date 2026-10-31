"""Deterministic enrichment: roster row -> dossier with sourced facts. No LLM.

  python -m outreach.enrich data/roster/cmu-stat.jsonl        # -> data/dossiers/cmu-stat.jsonl
  python -m outreach.enrich data/roster/cmu-stat.jsonl --only "Weijing Tang"

Per person it opens at most 2 pages (department profile + personal homepage), then:
  email      every address in the raw HTML (incl. obfuscated / cloudflare); keep only one that belongs to
             this person (name tokens/initials in the local part) and is on an official domain.
  links      homepage / lab / Google Scholar from link text + URL patterns (only links present on the page)
  title      roster title; position_class by regex
  research   the research paragraph (verbatim, <= 900 chars) for the LLM judge
  signals    verbatim sentences about recruiting students and start year
  papers     outreach.papers (OpenAlex with key, else Semantic Scholar disambiguated against page text)
Every fact carries {source_url, quote}; quotes are cut from the saved snapshot, so validate.py can re-check.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .config import ROOT, institution_domains
from .fetch import emails as find_emails, get, links as find_links, visible_text
from .validate import norm_name

OUT = ROOT / "data" / "dossiers"
TODAY = date.today().isoformat()

CLASS_RULES = [  # first match wins; order matters
    (r"emerit", "emeritus"),
    (r"teaching|lecturer|instructor|of the practice|clinical", "teaching"),
    (r"adjunct|affiliate|courtesy|visiting|postdoc|in residence", "other"),
    (r"incoming|starting (in )?(fall|spring|january|july)", "incoming_assistant"),
    (r"research (assistant |associate )?professor|research scientist|senior scientist", "research_faculty"),
    (r"assistant professor", "assistant"),
    (r"associate professor", "associate"),
    (r"professor|chair\b|university professor", "full"),
    (r"core (institute )?member|principal investigator|investigator|group leader|lab head|fellow\b", "institute_pi"),
]

HOMEPAGE_TEXT = re.compile(r"\b(personal (web)?site|home ?page|website|web ?page|lab(oratory)?( website| page)?|research group|group (website|page)|my site)\b", re.I)
SKIP_HOST = re.compile(r"(facebook|twitter|x\.com|linkedin|instagram|youtube|bsky|mastodon|orcid\.org|researchgate|"
                       r"doi\.org|arxiv\.org|pubmed|ncbi|scopus|webofscience|wikipedia|google\.com/maps)", re.I)
RECRUIT = re.compile(r"[^.!?\n]{0,200}\b(recruit\w*|looking for|seeking|accepting|taking (on )?new|openings?|positions? available|"
                     r"prospective (ph\.?d\.? )?students?|not (taking|accepting|recruiting))\b[^.!?\n]{0,200}[.!?]?", re.I)
STUDENTISH = re.compile(r"ph\.?d|graduate|student|postdoc", re.I)
START = re.compile(r"[^.!?\n]{0,120}\b(joined|joining|since|starting|will join|moved to)\b[^.!?\n]{0,60}\b(19|20)\d\d\b[^.!?\n]{0,80}", re.I)
RESEARCH_WORDS = re.compile(r"\b(research|interests?|work on|working on|focus(es)?|develop\w*|stud(y|ies))\b", re.I)


TITLE = re.compile(r"\b((?:incoming |tenure-track )?(?:assistant |associate |full |distinguished |university |research |adjunct |teaching |visiting )?"
                   r"professor(?: emerit\w+)?|(?:senior |principal )?research scientist|lecturer)\b(?: (?:of|in) [A-Z][\w&,. ]{3,60})?", re.I)


def find_title(vis: str, name: str) -> str:
    """First professor-like title in the first 3000 chars of the page (homepages put it under the name)."""
    head = vis[:3000]
    i = max(0, head.lower().find(norm_name(name).split()[-1]))
    m = TITLE.search(head, i) or TITLE.search(head)
    return m.group(0).strip(" ,.") if m else ""


# Applicant (2026-10-31): only people who can take PhD students. Research-track, teaching, adjunct are out;
# independent fellows (e.g. "CSHL Fellow") run their own groups and are in.
YOUNG = {"incoming_assistant", "assistant", "associate"}
FELLOW = re.compile(r"\b(cshl|independent|junior) fellow\b|\bfellow\b.*\b(lab|group)\b", re.I)


def young_title(title: str) -> bool:
    return position_class(title) in YOUNG or bool(FELLOW.search(title))


def position_class(title: str) -> str:
    t = title.lower()
    for pat, cls in CLASS_RULES:
        if re.search(pat, t):
            return cls
    return "other"


def _quote_around(text: str, needle: str, width: int = 70) -> str:
    i = text.lower().find(needle.lower())
    if i < 0:
        return ""
    return text[max(0, i - width): i + len(needle) + width].strip()


PERSONAL_MAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "me.com",
                 "protonmail.com", "proton.me", "qq.com", "163.com", "126.com", "foxmail.com"}


def pick_email(raw: str, url: str, name: str, institution: str, own_page: bool = False) -> dict | None:
    """The one address on this page that belongs to this person, with a verbatim quote. None if unsure."""
    toks = [t for t in norm_name(name).split() if len(t) >= 3]
    parts = norm_name(name).split()
    initials = "".join(t[0] for t in parts)
    domains = institution_domains(institution)
    vis = visible_text(raw)
    best, best_score = None, 0
    for em, _ctx in find_emails(raw):
        local, _, dom = em.partition("@")
        official = not domains or any(dom == d or dom.endswith("." + d) for d in domains)
        personal = dom in PERSONAL_MAIL or any(t in dom for t in toks)   # gmail etc., or their own vanity domain
        if not official and not (own_page and personal and any(t in local for t in toks + [dom.split(".")[0]])):
            continue   # never company addresses (meta.com, microsoft.com): outreach goes to the university role
        score = 0
        if any(t in local for t in toks):
            score = 3
        elif len(initials) >= 2 and (local.startswith(initials) or local.startswith(initials[0] + parts[-1][:3])):
            score = 2
        elif local.startswith(initials[:2]):
            score = 1
        if re.match(r"(info|admin|office|contact|help|web|dept|stat|grad|phd|chair|news|media)\b", local):
            score = 0
        if not official:
            score = min(score, 2)   # personal address: usable, flagged below for a human glance
        if score > best_score:
            best, best_score = em, score
    if not best:
        return None
    from .schema import deobfuscate, email_appears_in
    q = _quote_around(vis, best)
    if not q:   # obfuscated on the page: find the window whose de-obfuscation contains the address
        local = best.split("@")[0]
        i = vis.lower().find(local)
        while i >= 0 and not q:
            w = vis[max(0, i - 70): i + len(local) + 90]
            if email_appears_in(best, w):
                q = w.strip()
            i = vis.lower().find(local, i + 1)
    if not q:   # only in a mailto: href
        m = re.search(r"<a[^>]+mailto:" + re.escape(best) + r"[^>]*>.{0,120}?</a>", raw, re.I | re.S)
        q = " ".join(m.group(0).split()) if m else ""
    if not q or not email_appears_in(best, q):
        return None
    return {"value": best, "evidence": {"source_url": url, "quote": q[:300], "checked_on": TODAY}, "match": best_score}


def personal_site(url: str, name: str) -> bool:
    toks = [t for t in norm_name(name).split() if len(t) >= 3]
    return "/~" in url or any(t in url.lower() for t in toks) or not re.search(r"\.(edu|org|ac\.\w+)(/|$)", urlparse(url).netloc + "/")


def pick_links(raw: str, url: str, name: str) -> dict:
    out = {"homepage": None, "lab_website": None, "google_scholar": None, "cv": None, "pubs": None, "contact": None}
    host = urlparse(url).netloc
    toks = [t for t in norm_name(name).split() if len(t) >= 3]
    for text, href in find_links(raw, url):
        h = href.lower()
        if not h.startswith("http"):
            continue
        if "scholar.google" in h and "user=" in h and not out["google_scholar"]:
            uid = re.search(r"user=([\w-]+)", href).group(1)
            out["google_scholar"] = f"https://scholar.google.com/citations?user={uid}"
            continue
        if SKIP_HOST.search(h) or h.split("#")[0].rstrip("/") == url.lower().rstrip("/"):
            continue
        t = text.strip()
        offsite = urlparse(h).netloc != host or "/~" in h or any(t_ in h for t_ in toks)
        own_site = personal_site(url, name)
        if not offsite and not own_site:   # same-site links on a department page are navigation
            continue
        if re.search(r"\bcv\b|curriculum vitae|vita\b|resume", t, re.I) and not out["cv"]:
            out["cv"] = href
        elif re.fullmatch(r"contact( me| info(rmation)?)?", t, re.I) and not out["contact"]:
            out["contact"] = href
        elif re.fullmatch(r"(selected |recent |all )?(publications?|papers|preprints)", t, re.I) and not out["pubs"]:
            out["pubs"] = href
        elif re.search(r"\blab\b|laboratory|group", t, re.I) and HOMEPAGE_TEXT.search(t) and not out["lab_website"]:
            out["lab_website"] = href
        elif HOMEPAGE_TEXT.search(t) and len(t) < 40 and not out["homepage"]:
            out["homepage"] = href
        elif not out["homepage"] and any(t_ in h for t_ in toks) and \
                re.search(r"github\.io|sites\.google|/~|people|faculty|\.com/?$|\.org/?$|\.net/?$", h):
            out["homepage"] = href   # e.g. https://jdoe.github.io linked from the profile
    return out


GOOD = re.compile(r"\b(my research|research (focuses|interests?|is|centers|lies|spans|program)|interested in|i work on|"
                  r"we (develop|study|work)|our (lab|group|research)|focus(es)? on|aims? to|methods? for)\b", re.I)
BIO = re.compile(r"\b(received|graduated|ph\.?d\.? (from|in)|postdoc\w*|prior to|previously|was a|b\.?s\.?|m\.?s\.?|"
                 r"fellowship|award\w*|born)\b", re.I)


def research_text(raw: str) -> str:
    """Verbatim research description: the paragraph that talks most about research and least about career."""
    soup = BeautifulSoup(raw, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        t.decompose()
    cands = []
    for el in soup.find_all(["p", "li", "div", "td"]):
        if el.find(["p", "div", "li"]):          # leaf-ish blocks only
            continue
        s = " ".join(el.get_text(" ").split())
        if 100 < len(s) < 2500:
            cands.append(s)
    if not cands:   # plain text (PDF) or unusual markup: split visible text into sentence windows
        txt = visible_text(raw)
        cands = [txt[i:i + 700] for i in range(0, min(len(txt), 6000), 350)]
    nav = re.compile(r"skip to|sign up|contact us|toggle|main navigation|newsletter|search menu|utility", re.I)
    cands = [c for c in cands if len(nav.findall(c)) < 2]   # menus and footers are not research descriptions
    def score(s: str) -> float:
        return 3 * len(GOOD.findall(s)) + len(RESEARCH_WORDS.findall(s)) - 2 * len(BIO.findall(s)) + min(len(s), 600) / 300
    best = max(cands, key=score, default="")
    return best[:900] if best and score(best) > 2 else ""


def signals(raw: str, url: str) -> dict:
    vis = visible_text(raw)
    rec = []
    for m in RECRUIT.finditer(vis):
        s = m.group(0).strip()
        if STUDENTISH.search(s) and len(s) > 25 and s not in rec:
            rec.append(s[:300])
    start = [m.group(0).strip()[:250] for m in START.finditer(vis)][:3]
    years = [int(y) for y in re.findall(r"\b(20[0-3]\d)\b", " ".join(rec))]
    return {"recruiting": [{"source_url": url, "quote": q, "years": years} for q in rec[:4]],
            "start": [{"source_url": url, "quote": q} for q in start]}


def enrich(row: dict, with_papers: bool = True) -> dict:
    from .roster import clean_name
    row = {**row, "name": clean_name(row["name"])}
    d = {k: row.get(k) for k in ("name", "institution", "department", "title_on_roster", "roster_url", "profile_url", "filter", "ai_venues", "first_paper", "heritage")}
    d["position_class"] = position_class(row.get("title_on_roster") or "")
    d["position"] = {"value": row.get("title_on_roster") or "", "evidence": {
        "source_url": row["roster_url"], "quote": row["quote"], "checked_on": TODAY}}
    d.update(email=None, homepage=None, lab_website=None, google_scholar=None, cv=None,
             pubs=None, contact=None, research={"text": "", "source_url": None}, recruiting=[], start=[], papers=[], problems=[])
    if (row.get("profile_url") or "").startswith("mailto:"):   # directory linked the address instead of a profile
        d["email"] = pick_email(row["quote"], row["roster_url"], row["name"], row["institution"])
        if not d["email"]:   # the address sits in the href only: take it from the directory page, name-matched
            e = pick_email(get(row["roster_url"]), row["roster_url"], row["name"], row["institution"])
            d["email"] = e if e and e["match"] == 3 else None
        row = {**row, "profile_url": None}
        if d["email"]:
            d["email"].pop("match", None)
    if row.get("ps_papers"):   # found through papers (outreach/papersource.py): papers come with the row
        d["papers"] = row["ps_papers"]
        d["position"] = {"value": f"PI (last author of {row['ps_n']} recent papers at this institution)",
                         "evidence": {"source_url": row["roster_url"], "quote": row["quote"], "checked_on": TODAY}}
        d["position_class"] = "pi_from_papers"
    pages = []
    for k in ("google_scholar", "homepage"):
        d[k] = d[k] or row.get(k)
    for u in (row.get("profile_url"), row.get("homepage")):
        if u and u not in pages:
            pages.append(u)
    i = 0
    while i < len(pages) and i < 3:
        u = pages[i]
        i += 1
        try:
            raw = get(u)
        except Exception as e:  # noqa: BLE001 - record and move on; a missing page is not fatal
            d["problems"].append(f"fetch {u}: {type(e).__name__} {str(e)[:80]}")
            continue
        if not d["email"]:
            d["email"] = pick_email(raw, u, row["name"], row["institution"], own_page=personal_site(u, row["name"]))
        if not d["position"]["value"]:   # CSRankings rows have no title: take it from the homepage, with a quote
            vis = visible_text(raw)
            t = find_title(vis, row["name"])
            if t:
                d["position"] = {"value": t, "evidence": {"source_url": u, "quote": _quote_around(vis, t, 60)[:300], "checked_on": TODAY}}
                d["position_class"] = position_class(t)
                if d["position_class"] not in YOUNG | {"other"}:
                    d["problems"].append(f"skipped: senior title on profile ({t})")
                    return d   # early stop: no homepage / papers for senior faculty
        for k, v in pick_links(raw, u, row["name"]).items():
            if v and not d[k] and v not in pages:
                d[k] = v
        if d["homepage"] and d["homepage"] not in pages and len(pages) < 3:
            pages.append(d["homepage"])
        if not d["email"] and d.get("contact") and d["contact"] not in pages and len(pages) < 3:
            pages.append(d["contact"])
        rt = research_text(raw)
        if rt and (not d["research"]["text"] or _rscore(rt) > _rscore(d["research"]["text"])):
            d["research"] = {"text": rt, "source_url": u}
        s = signals(raw, u)
        d["recruiting"] += s["recruiting"]
        d["start"] += s["start"]
    if not d["email"] and d["cv"]:   # pilot: Townes, Nugent list their address only in the CV PDF
        try:
            d["email"] = pick_email(get(d["cv"]), d["cv"], row["name"], row["institution"])
            pages.append(d["cv"])
        except Exception as e:  # noqa: BLE001
            d["problems"].append(f"fetch cv: {type(e).__name__}")
    if not d["email"] and row.get("block_email"):   # mailto inside this person's own directory block
        from .schema import email_appears_in
        dom = row["block_email"].split("@")[1].lower()
        doms = institution_domains(row["institution"])
        if email_appears_in(row["block_email"], row["block_email_quote"]) and any(dom == x or dom.endswith("." + x) for x in doms):
            d["email"] = {"value": row["block_email"].lower(), "evidence": {"source_url": row["roster_url"],
                          "quote": row["block_email_quote"], "checked_on": TODAY}}
    if not d["email"] and row.get("roster_url", "").startswith("http") and "csrankings" not in row["roster_url"]:
        try:   # directory pages often carry mailto: links; accept only a full name-token match
            e = pick_email(get(row["roster_url"]), row["roster_url"], row["name"], row["institution"])
            if e and e["match"] == 3:
                d["email"] = e
        except Exception:  # noqa: BLE001
            pass
    if with_papers and not row.get("ps_papers"):
        from .papers import find_papers
        page_text = " ".join(visible_text(get(u)) for u in pages if _cached(u))
        res = find_papers(row["name"], row["institution"], page_text)
        if res.get("problem") and (d["pubs"] or d["cv"]):  # publication list / CV confirms the right same-name author
            extra = []
            for u in (d["pubs"], d["cv"]):
                try:
                    extra.append(visible_text(get(u))) if u else None
                except Exception:  # noqa: BLE001
                    pass
            res = find_papers(row["name"], row["institution"], page_text + " " + " ".join(extra))
        d["papers"], d["papers_author"] = res.get("papers", []), res.get("author")
        d["first_paper"] = d.get("first_paper") or res.get("first_year")
        if res.get("warning"):
            d["problems"].append(res["warning"])
        if res.get("problem"):
            d["problems"].append(res["problem"])
    if not with_papers:
        d["problems"].append("papers: deferred")   # refilled later, only for people the judge finds relevant
    if d["email"] and d["email"].pop("match", 3) < 2:
        d["problems"].append("email matched by initials only or non-university address: human check")
    return d


def refill_papers(path: Path) -> None:
    from .papers import find_papers
    from .judge import JOUT, slug_id
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    judged = {j["id"]: j for f in JOUT.glob(f"{path.stem}_*.jsonl") for j in
              (json.loads(l) for l in f.read_text().splitlines() if l.strip())}
    n = 0
    for d in rows:
        j = judged.get(slug_id(d["name"], d["institution"]))
        from .score import score
        rel = j.get("relevance") if j else score(d)["relevance"]
        if d["research"]["text"] and rel == "no":
            continue   # papers only for people the judge kept: saves the OpenAlex daily budget
        if d["papers"] or not any(p.startswith("papers:") and ("rate limited" in p or "budget" in p or "deferred" in p) for p in d["problems"]):
            continue
        pages = [u for u in (d.get("profile_url"), d.get("homepage"), d.get("pubs")) if u and _cached(u)]
        res = find_papers(d["name"], d["institution"], " ".join(visible_text(get(u)) for u in pages))
        d["papers"], d["first_paper"] = res.get("papers", []), d.get("first_paper") or res.get("first_year")
        d["problems"] = [p for p in d["problems"] if not p.startswith("papers:")] + \
            [x for x in (res.get("problem"), res.get("warning")) if x]
        n += bool(d["papers"])
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
    print(f"{path.name}: papers refilled for {n}")


def official_profiles(skip: Path) -> dict:
    out = {}
    for f in sorted((ROOT / "data" / "roster").glob("*.jsonl")):
        if f == skip or f.name.startswith("csr-"):
            continue
        for l in f.read_text().splitlines():
            if l.strip() and not l.startswith('{"_'):
                r = json.loads(l)
                if r.get("profile_url"):
                    out.setdefault((norm_name(r["name"]), r["institution"]), r)
    return out


def _rscore(s: str) -> int:
    return 3 * len(GOOD.findall(s)) - 2 * len(BIO.findall(s))


def _cached(url: str) -> bool:
    from .fetch import SNAP, snapshot_path
    return snapshot_path(SNAP, url).exists()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roster", type=Path)
    ap.add_argument("--only")
    ap.add_argument("--no-papers", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--all-ranks", action="store_true", help="also full / emeritus / teaching faculty")
    ap.add_argument("--heritage", help="only rows with this surname tag (e.g. chinese), filtered before any fetch")
    ap.add_argument("--refill-papers", action="store_true", help="retry papers only, for dossiers that failed (rate limits)")
    a = ap.parse_args()
    if a.refill_papers:
        return refill_papers(OUT / a.roster.name)
    rows = [json.loads(l) for l in a.roster.read_text().splitlines() if l.strip() and not l.startswith('{"_')]
    official = official_profiles(a.roster)
    for r in rows:   # CSRankings rows: use the department's own profile page (email, title) when one exists
        o = official.get((norm_name(r["name"]), r["institution"]))
        if o and r["roster_url"].startswith("https://csrankings"):
            r.update(profile_url=o["profile_url"], title_on_roster=o["title_on_roster"], roster_url=o["roster_url"],
                     quote=o["quote"], department=o["department"])
    if a.only:
        rows = [r for r in rows if r["name"] == a.only]
    elif not a.all_ranks:   # applicant wants young faculty only: drop senior / non-advising titles before any fetch
        from .roster import faculty_like
        rows = [r for r in rows if faculty_like(r) and
                (not r.get("title_on_roster") or young_title(r["title_on_roster"]))]
    from .surnames import PRIORITY, asian_tag
    for r in rows:
        r["heritage"] = r.get("heritage") or asian_tag(r["name"])
    if a.heritage:
        rows = [r for r in rows if r["heritage"] == a.heritage]
    rows.sort(key=lambda r: PRIORITY[r["heritage"]])
    with ThreadPoolExecutor(a.workers) as ex:
        out = list(ex.map(lambda r: enrich(r, not a.no_papers), rows))
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / a.roster.name
    if a.only and dest.exists():
        keep = [json.loads(l) for l in dest.read_text().splitlines() if l.strip()]
        out = [x for x in keep if x["name"] != a.only] + out
    dest.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out))
    n = len(out)
    print(f"{dest}: {n} people | email {sum(bool(x['email']) for x in out)} | homepage {sum(bool(x['homepage']) for x in out)}"
          f" | research {sum(bool(x['research']['text']) for x in out)} | papers {sum(bool(x['papers']) for x in out)}"
          f" | recruiting-signal {sum(bool(x['recruiting']) for x in out)} | problems {sum(bool(x['problems']) for x in out)}")


if __name__ == "__main__":
    main()
