"""Run this on YOUR OWN computer (OpenReview challenges cloud IPs). Public data only, no login.

  pip install requests
  python tools/openreview_export.py            # -> openreview_lab_history.jsonl (send this file back)

It reads the author lists of accepted ICLR 2025 / NeurIPS 2024 / ICML 2025 papers, then those authors' public
OpenReview profiles (education + work history), and keeps people whose CURRENT position is at one of the labs below.
~800 requests (profiles are fetched 50 at a time), 2 per second: about 7-10 minutes. Stop any time; partial output is kept.
"""
import json
import re
import time

import requests

API = "https://api2.openreview.net"
VENUES = ["ICLR.cc/2025/Conference", "NeurIPS.cc/2024/Conference", "ICML.cc/2025/Conference"]
LABS = re.compile(r"deepmind|google|meta|facebook|microsoft|nvidia|apple|amazon|allen institute|ai2|flatiron|isomorphic|"
                  r"genentech|prescient|chan zuckerberg|biohub|toyota research|ibm", re.I)
S = requests.Session()
S.headers["User-Agent"] = "phd-applicant-research (personal use)"


def get(path, **params):
    time.sleep(0.5)
    r = S.get(API + path, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def authors(venue):
    ids, offset = set(), 0
    while True:
        notes = get("/notes", **{"content.venueid": venue, "limit": 1000, "offset": offset}).get("notes", [])
        if not notes:
            return ids
        for n in notes:
            ids.update(a for a in n.get("content", {}).get("authorids", {}).get("value", []) if a.startswith("~"))
        offset += 1000


def main():
    ids = set()
    for v in VENUES:
        a = authors(v)
        print(v, len(a), "authors")
        ids |= a
    ids = sorted(ids)
    with open("openreview_lab_history.jsonl", "w") as out:
        for i in range(0, len(ids), 50):
            for p in get("/profiles", ids=",".join(ids[i:i + 50])).get("profiles", []):
                hist = p.get("content", {}).get("history", [])
                cur = [h for h in hist if not h.get("end")]
                if any(LABS.search((h.get("institution") or {}).get("name", "")) for h in cur):
                    out.write(json.dumps({"id": p["id"], "name": (p.get("content", {}).get("names") or [{}])[0].get("fullname"),
                                          "history": hist, "relations": p.get("content", {}).get("relations", [])}) + "\n")
            out.flush()
            print(f"{i + 50}/{len(ids)} profiles checked")


if __name__ == "__main__":
    main()
