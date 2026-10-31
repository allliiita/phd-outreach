"""USF directories mix several card layouts per page, so one CSS selector cannot read them all.
Per card: name = first person-shaped text among gv-name / img-alt / heading / strong / link (degrees stripped
by roster.clean_name), title = first line holding a title word. Everything is copied from the page.
  python -m outreach.roster_usf SLUG
"""
from __future__ import annotations
import json, re, sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .fetch import get
from .roster import clean_name, TITLE_WORD, _mailto, LAST_FIRST

INST = "University of South Florida"
CFG = {
 "usf-bellini": ("Bellini College of AI, Cybersecurity and Computing", "https://www.usf.edu/ai-cybersecurity-computing/people/faculty/index.aspx", "div.snippetImageGrid_item", None),
 "usf-ee": ("Electrical Engineering", "https://www.usf.edu/engineering/ece/faculty-staff/index.aspx", "div.snippetImageGrid_item", None),
 "usf-bme": ("Medical Engineering (BME)", "https://www.usf.edu/engineering/bme/faculty-staff/index.aspx", "div.snippetImageGrid_item", r"core faculty"),
 "usf-chem": ("Chemistry", "https://www.usf.edu/arts-sciences/departments/chemistry/faculty/index.aspx", "div.snippetImageGrid_item", None),
 "usf-mpp": ("Molecular Pharmacology and Physiology", "https://health.usf.edu/medicine/mpp/faculty/", "li.col", None),
 "usf-molmed": ("Molecular Medicine", "https://health.usf.edu/medicine/molecularmedicine/faculty/", "li.col", None),
}
RANK = re.compile(r"^((?:(?:Chair|Assoc\. Dean)\s*&\s*)?(?:Research |Assistant |Associate |Distinguished )*Professor(?: of Molecular Medicine)?)\b")
SKIP_NAME = re.compile(r"campus|^email$|^about$|website|genealogy|scholar|^office|video|^lab\b", re.I)

def lines_of(el):
    for br in el.find_all("br"):
        br.replace_with("\n")
    return [" ".join(l.split()) for l in el.get_text("\n").split("\n") if l.strip()]

def person_name(el):
    cands = []
    g = el.select_one(".gv-name")
    if g: cands.append(g.get_text(" "))
    for t in el.find_all(["h4", "h3", "strong", "a"]):
        cands.append(t.get_text(" "))
    img = el.find("img")
    if img and img.get("alt"): cands.append(img["alt"])
    for c in cands:
        c = " ".join(c.split()).strip(" ,")
        if not c or SKIP_NAME.search(c): continue
        c = re.sub(r"^(Prof\.|Dr\.)\s+", "", c)
        c = c.split(",")[0] if re.search(r",\s*(Jr|Sr|II|III)\.?$", c) is None and "," in c and not LAST_FIRST.match(c) else c
        c = re.sub(r",\s*(Jr|Sr)\.?$", "", c)
        c = clean_name(c)
        m = LAST_FIRST.match(c)
        if m: c = f"{m.group(2)} {m.group(1)}"
        if re.match(r"^[A-Z][\w'’.\-()\"]+(?: [A-Z\"(][\w'’.\-()\"]*| (?:van|de|der|von|da|di|la|le)){1,5}$", c) and not TITLE_WORD.search(c):
            return c
    return ""

def run(slug):
    unit, url, sel, only = CFG[slug]
    soup = BeautifulSoup(get(url), "html.parser")
    rows = []
    for card in soup.select(sel):
        h = card.find_previous(["h2", "h3"]); section = " ".join(h.get_text(" ").split()) if h else ""
        if only and not re.search(only, section, re.I): continue
        jt = card.select_one(".job-title")
        mail = _mailto(card)
        quote = " ".join(card.get_text(" ").split())[:300]
        name = person_name(card)
        if not name: print("NO NAME:", quote[:80]); continue
        ls = lines_of(card)
        if jt: title = " ".join(jt.get_text(" ").split())
        else:
            title = next((l for l in ls if TITLE_WORD.search(l) and len(l) < 150 and name.split()[-1] not in l[:len(name)+3]), "")
        a = card.select_one("a.gv-link, h4 a, p a, a[href]")
        a = next((x for x in card.find_all("a", href=True) if not x["href"].startswith(("mailto:", "http", "#", "JavaScript")) and "images" not in x["href"]), None) or next((x for x in card.find_all("a", href=True) if x["href"].startswith("http") and "usf.edu" in x["href"] and "scholar" not in x["href"]), None)
        name = re.sub(r"^(DPhil|PhD|MD)\s+", "", name)
        if slug == "usf-molmed":   # page merges research area into the title line: keep the leading rank only
            m = RANK.match(title)
            if not title or not m or re.match(r"Research Associate", title): continue
            title_raw, title = title, m.group(1).strip()
        elif slug == "usf-chem" and not title: continue   # blank-title rows are staff (Figueroa, Hoare, Nelson)
        rows.append({"name": name, "institution": INST, "department": unit, "title_on_roster": title, "roster_url": url,
                     "profile_url": urljoin(url, a["href"]) if a else None, "quote": quote, "filter": "all",
                     "section": section, **({"title_raw": title_raw} if slug == "usf-molmed" and title_raw != title else {}), **mail})
    seen, out = set(), []
    for r in rows:
        if r["name"].lower() not in seen: seen.add(r["name"].lower()); out.append(r)
    open(f"data/roster/{slug}.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in out))
    print(slug, len(out), "blank titles:", sum(not r["title_on_roster"] for r in out))
    return out

if __name__ == "__main__":
    for s in sys.argv[1:]: run(s)
