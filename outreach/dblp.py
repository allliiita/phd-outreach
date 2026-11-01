"""Top-ML-venue output per person from the official dblp XML dump (dblp.org/xml/dblp.xml.gz, streamed once,
not saved). The dblp search API is behind a bot check, so we use the dump dblp publishes for bulk use.

  python -m outreach.dblp            # -> data/dblp.jsonl  {id, pid, match, venues_23_26:{venue:n}, ml_top, total_23_26}

Disambiguation is deterministic: dblp person records (<www key="homepages/...">) carry affiliation notes and
homepage URLs. A dblp person is accepted only if its affiliation note names the institution, or one of its URLs
equals the person's homepage / official page host path. Same-name people without such evidence -> no match.
"""
from __future__ import annotations

import gzip
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from xml.etree.ElementTree import iterparse

from .config import ROOT

DATA = ROOT / "data"
DUMP = "https://dblp.org/xml/dblp.xml.gz"
YEARS = range(2023, 2027)
TOP = re.compile(r"^(NeurIPS|ICML|ICLR|CVPR|ICCV|ECCV|ACL|EMNLP|NAACL|AAAI|IJCAI|KDD|AISTATS|UAI|COLT|MICCAI|"
                 r"WACV|CoRL|ICRA|IROS|RSS|COLM|Trans\. Mach\. Learn\. Res\.|J\. Mach\. Learn\. Res\.|"
                 r"IEEE Trans\. Pattern Anal\. Mach\. Intell\.|Nat\. Mac\. Intell\.|NeurIPS Datasets and Benchmarks)",
                 re.I)
# expand short institution names to the words that appear in dblp affiliation notes
INST_WORDS = {"Boston University": ["boston university", "boston univ"], "Duke University": ["duke"],
              "University of South Florida": ["south florida", "usf"],
              "University of California San Francisco": ["san francisco", "ucsf"],
              "Cold Spring Harbor Laboratory": ["cold spring harbor"],
              "Icahn School of Medicine at Mount Sinai": ["mount sinai", "icahn"]}


def ascii_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"\s+\d{4}$", "", s).split()).lower()   # dblp homonyms: "Sifan Liu 0002"


def run() -> None:
    people = [json.loads(l) for l in (DATA / "tag" / "people.jsonl").read_text().splitlines() if l.strip()]
    want = defaultdict(list)
    for p in people:
        want[ascii_name(p["name"])].append(p)
    persons: dict[str, dict] = {}            # dblp author string -> {notes, urls}
    pubs: dict[str, Counter] = defaultdict(Counter)
    titles: dict[str, list] = defaultdict(list)
    curl = subprocess.Popen(["curl", "-sL", DUMP], stdout=subprocess.PIPE)
    stream = _Entities(gzip.GzipFile(fileobj=curl.stdout))
    ctx = iterparse(stream, events=("end",))
    n = 0
    for _, el in ctx:
        tag = el.tag
        if tag in ("article", "inproceedings", "www"):
            authors = [a.text or "" for a in el.findall("author")]
            hit = [a for a in authors if ascii_name(a) in want]
            if hit:
                if tag == "www" and (el.get("key") or "").startswith("homepages/"):
                    for a in hit:
                        rec = persons.setdefault(a, {"notes": [], "urls": []})
                        rec["notes"] += [x.text or "" for x in el.findall("note")]
                        rec["urls"] += [x.text or "" for x in el.findall("url")]
                else:
                    y = int((el.findtext("year") or "0")[:4] or 0)
                    if y in YEARS:
                        venue = el.findtext("booktitle") or el.findtext("journal") or ""
                        for a in hit:
                            pubs[a][venue] += 1
                            titles[a].append(el.findtext("title") or "")
            el.clear()
            n += 1
            if n % 2_000_000 == 0:
                print(f"{n:,} records", flush=True)
    curl.wait()
    (DATA / "dblp_raw.json").write_text(json.dumps({"persons": persons, "pubs": pubs, "titles": titles}))
    match()


def match() -> None:
    """Pick the dblp author for each person from data/dblp_raw.json (no re-download needed to change rules)."""
    raw = json.loads((DATA / "dblp_raw.json").read_text())
    persons, pubs, titles = raw["persons"], {k: Counter(v) for k, v in raw["pubs"].items()}, raw["titles"]
    people = [json.loads(l) for l in (DATA / "tag" / "people.jsonl").read_text().splitlines() if l.strip()]
    norm = lambda t: " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())[:60]
    out = []
    for p in people:
        k = ascii_name(p["name"])
        words = INST_WORDS.get(p["institution"], [p["institution"].lower()])
        hp = {u.rstrip("/").lower() for u in (p.get("homepage"), p.get("profile_url")) if u}
        cands = [a for a in set(persons) | set(pubs) if ascii_name(a) == k]
        ok = []
        for a in cands:
            rec = persons.get(a, {"notes": [], "urls": []})
            if any(w in " ".join(rec["notes"]).lower() for w in words) or \
                    any(u.rstrip("/").lower() in hp for u in rec["urls"]):
                ok.append(a)
        known = {norm(x["title"]) for x in p.get("papers") or []}
        by_title = [a for a in cands if known & {norm(t) for t in titles.get(a, [])}]
        if len(ok) == 1:
            a, match = ok[0], "affiliation/homepage"
        elif len(by_title) == 1:
            a, match = by_title[0], "shared paper title"
        elif not ok and len(cands) == 1 and not re.search(r"\d{4}$", cands[0]):
            a, match = cands[0], "unique dblp name (unnumbered), unverified"
        else:
            out.append({"id": p["id"], "pid": None, "match": f"none ({len(cands)} dblp candidates)"})
            continue
        v = pubs.get(a, Counter())
        top = {x: c for x, c in v.items() if TOP.match(x)}
        out.append({"id": p["id"], "pid": a, "match": match, "ml_top": sum(top.values()),
                    "venues_23_26": dict(sorted(top.items(), key=lambda t: -t[1])), "total_23_26": sum(v.values())})
    (DATA / "dblp.jsonl").write_text("".join(json.dumps(o) + "\n" for o in out))
    print(f"{len(out)} people, matched {sum(o['pid'] is not None for o in out)}, "
          f"with top-venue papers {sum((o.get('ml_top') or 0) > 0 for o in out)}")


class _Entities:
    """dblp.xml uses HTML entities declared in dblp.dtd (e.g. &eacute;). The file is line-based, so replace
    them line by line with their characters (XML-escaped where needed) before expat sees them."""
    def __init__(self, f):
        import html.entities
        self.f, self.buf = f, b""
        m = {k: f"&#{c};" for k, c in html.entities.name2codepoint.items()}   # numeric refs: encoding-safe
        keep = {"amp", "lt", "gt", "quot", "apos"}
        self.sub = lambda line: re.sub(rb"&([A-Za-z][A-Za-z0-9]*);",
                                       lambda x: x.group(0) if x.group(1).decode() in keep else
                                       m.get(x.group(1).decode(), "").encode(), line)

    def read(self, n: int = -1) -> bytes:
        while (n < 0 or len(self.buf) < n):
            line = self.f.readline()
            if not line:
                break
            if line.startswith(b"<!DOCTYPE"):
                continue
            self.buf += self.sub(line)
        out, self.buf = (self.buf, b"") if n < 0 else (self.buf[:n], self.buf[n:])
        return out


if __name__ == "__main__":
    import sys
    match() if sys.argv[1:] == ["match"] else run()
