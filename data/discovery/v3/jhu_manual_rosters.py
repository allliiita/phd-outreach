"""JHU pages the applicant saved in her own browser (engineering.jhu.edu / ai.jhu.edu are bot-checked for us).
Names, titles, departments and emails are parsed by code from data/snapshots/manual/jhu-*.txt."""
import json, re

def blocks(src, url, unit):
    """ECE / Whiting layout: Name, (profile-url lines), Title, DEPARTMENT ..., EMAIL."""
    L = [l.strip() for l in open(f"data/snapshots/manual/{src}.txt") if l.strip()]
    out, i = [], 0
    while i < len(L) - 2:
        if L[i + 1].startswith("(https://engineering.jhu.edu/") and re.match(r"^[A-Z][\w'’.\- ()\"]+$", L[i]):
            name = re.sub(r"\s*\(https?://.*$", "", L[i]).strip()
            j = i + 1
            prof = ""
            while j < len(L) and (L[j].startswith("(") or L[j].endswith("/)") or "/)" in L[j]) and j < i + 4:
                prof += L[j]; j += 1
            title = L[j] if j < len(L) else ""
            dept, k = [], j + 1
            while k < len(L) and k < j + 6 and L[k].isupper() and "@" not in L[k]:
                dept.append(L[k]); k += 1
            email = next((re.search(r"[\w.\-]+@[\w.\-]+", x).group(0).lower() for x in L[j:j + 8] if "@" in x), "")
            m = re.search(r"\((https://[^)]+)", prof)
            out.append({"name": name, "institution": "Johns Hopkins University", "department": unit if unit else " ".join(dept).title()[:80],
                        "title_on_roster": title, "roster_url": url, "profile_url": m.group(1) if m else "",
                        "quote": f"{name} {title} {' '.join(dept)} {email}".strip(), "block_email": email,
                        "block_email_quote": f"{name} {title} {email}", "source": f"applicant-saved page data/snapshots/manual/{src}.pdf"})
            i = k
        else:
            i += 1
    return out

def dsai():
    """'Name (profile-url), assistant professor in the Department of X. ...' — wording after the title varies."""
    t = " ".join(l.strip() for l in open("data/snapshots/manual/jhu-dsai-22-new.txt") if l.strip())
    out = []
    for m in re.finditer(r"([A-Z][\w'’.\-]+(?: \([^)]{1,20}\))?(?: [A-Z][\w'’.\-]+){1,3}) \((https?://[^)]+)\), ([^.]{0,120})", t):
        tm = re.match(r"((?:Bloomberg Distinguished |research )?(?:assistant |associate |full )?professor(?: of research)?)\s*(?:in|of)?\s*(?:the )?(.*)", m.group(3), re.I)
        if not tm:
            continue
        out.append({"name": m.group(1), "institution": "Johns Hopkins University",
                    "department": "DSAI new faculty 2025: " + tm.group(2).strip()[:70],
                    "title_on_roster": tm.group(1).strip(), "roster_url": "https://ai.jhu.edu/news/data-science-and-ai-institute-announces-22-new-faculty/",
                    "profile_url": m.group(2), "quote": m.group(0)[:300], "source": "applicant-saved page data/snapshots/manual/jhu-dsai-22-new.pdf"})
    return out

for slug, rows in [("jhu-ece", blocks("jhu-ece-people", "https://engineering.jhu.edu/ece/faculty/", "Electrical & Computer Engineering")),
                   ("jhu-whiting-new-faculty", blocks("jhu-whiting-new-faculty", "https://engineering.jhu.edu/faculty-staff/new-faculty/", "")),
                   ("jhu-dsai-new-faculty", dsai())]:
    seen, uniq = set(), []
    for r in rows:
        if r["name"] not in seen:
            seen.add(r["name"]); uniq.append(r)
    open(f"data/roster/{slug}.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in uniq))
    print(slug, len(uniq), "rows;", sum(bool(r.get("block_email")) for r in uniq), "with email")
