"""Run on YOUR OWN computer (OpenReview challenges cloud IPs). Public data only, no login. ~5 minutes.

  pip install requests
  python tools/openreview_lineage.py tools/our_professors.txt     # -> openreview_lineage.jsonl (upload it like last time)

For each professor on our list: find their OpenReview profile (by name + institution), read their own PhD/postdoc
advisors, and their PhD/postdoc ADVISEES' histories (internships and jobs at labs). This tells us where a lab's
students go, which is the resource signal the applicant cares about.
"""
import json
import re
import sys
import time

import requests

API = "https://api2.openreview.net"
S = requests.Session()
S.headers["User-Agent"] = "phd-applicant-research (personal use)"


def get(path, **params):
    time.sleep(0.4)
    r = S.get(API + path, params=params, timeout=60)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


def find(name, inst):
    res = get("/profiles/search", fullname=name, limit=10).get("profiles", [])
    key = re.sub(r"[^a-z]", "", inst.lower())[:12]
    for p in res:
        hist = p.get("content", {}).get("history", [])
        if any(key[:8] in re.sub(r"[^a-z]", "", ((h.get("institution") or {}).get("name") or "").lower()) for h in hist if not h.get("end")):
            return p
    return None


def main(path):
    rows = [l.rstrip("\n").split("\t") for l in open(path) if l.strip()]
    with open("openreview_lineage.jsonl", "w") as out:
        for pid, name, inst in rows:
            p = find(name, inst)
            if not p:
                out.write(json.dumps({"id": pid, "name": name, "found": False}) + "\n")
                continue
            rel = p.get("content", {}).get("relations", [])
            mine = [r for r in rel if re.search(r"advisor", r.get("relation", ""), re.I)]
            kids = [r for r in rel if re.search(r"advisee", r.get("relation", ""), re.I) and r.get("username")]
            kid_hist = []
            ids = [k["username"] for k in kids][:40]
            for i in range(0, len(ids), 40):
                for q in get("/profiles", ids=",".join(ids[i:i + 40])).get("profiles", []):
                    kid_hist.append({"id": q["id"], "history": q.get("content", {}).get("history", [])})
            out.write(json.dumps({"id": pid, "name": name, "found": True, "or_id": p["id"],
                                  "history": p.get("content", {}).get("history", []), "own_advisors": mine,
                                  "advisees": kids, "advisee_histories": kid_hist}) + "\n")
            out.flush()
            print(name, "advisees:", len(kids))


if __name__ == "__main__":
    main(sys.argv[1])
