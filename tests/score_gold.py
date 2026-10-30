"""Gold-set eval: compare blind worker output to human-checked records.

  python -m tests.score_gold tests/gold/people.jsonl data/eval_run/people.jsonl

Email precision must be 100% (a wrong address is never acceptable); a missing email costs recall only.
"""
import json
import sys
from pathlib import Path


def load(p):
    return {r["id"]: r for r in (json.loads(l) for l in Path(p).read_text().splitlines() if l.strip())}


def main():
    gold, run = load(sys.argv[1]), load(sys.argv[2])
    fields = ["position_class", "tier", "relevance", "homepage", "google_scholar"]
    hit = tot = 0
    em_tp = em_fp = em_fn = 0
    paper_bad = 0
    missing = [k for k in gold if k not in run]
    for k, g in gold.items():
        r = run.get(k)
        if not r:
            continue
        for f in fields:
            tot += 1
            hit += (str(g.get(f) or "").rstrip("/") == str(r.get(f) or "").rstrip("/"))
        ge = (g.get("email") or {}).get("value", "").lower()
        re_ = (r.get("email") or {}).get("value", "").lower()
        if re_ and re_ == ge:
            em_tp += 1
        elif re_ and re_ != ge:
            em_fp += 1
            print(f"WRONG EMAIL {k}: {re_} (gold {ge or 'none'})")
        elif ge and not re_:
            em_fn += 1
        gold_titles = {p["title"].lower() for p in g.get("recent_papers", [])}
        for p in r.get("recent_papers", []):
            if gold_titles and p["title"].lower() not in gold_titles and not g.get("_papers_open"):
                paper_bad += 1
    print(f"people recall {1 - len(missing)/len(gold):.1%}  missing={missing}")
    print(f"field accuracy {hit/tot:.1%}")
    print(f"email precision {em_tp/max(1, em_tp+em_fp):.1%}  recall {em_tp/max(1, em_tp+em_fn):.1%}")
    print(f"papers not in gold list: {paper_bad} (check by hand; gold may list only some)")
    ok = em_fp == 0 and hit / tot >= 0.95 and not missing
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
