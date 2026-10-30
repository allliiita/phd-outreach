"""Trust levels per pipeline stage, driven by measured audit error rates (not by feel).

Level 0  every output is verified by an independent agent AND shown to the human
Level 1  every output is verified by an independent agent; human sees a 10% sample
Level 2  independent verifier audits a 30% random sample; human sees failures only
Level 3  verifier audits 10%; deterministic checks on 100%

Promotion: only a human runs `python -m outreach.trust promote STAGE`, and only when the last
>=40 audited items have error rate <= 3% (gold-set eval also passing for that stage).
Demotion: automatic, as soon as the rolling error rate over the last 40 audits exceeds 10%.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path

from .config import ROOT

STATE = ROOT / "data" / "trust.json"
AUDITS = ROOT / "data" / "audits.jsonl"
SAMPLE = {0: 1.0, 1: 1.0, 2: 0.3, 3: 0.1}
WINDOW, PROMOTE_MAX, DEMOTE_MIN = 40, 0.03, 0.10
STAGES = ["departments", "roster", "profile", "email_draft"]


def _state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {s: 0 for s in STAGES}


def _save(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1))


def level(stage: str) -> int:
    return _state().get(stage, 0)


def should_audit(stage: str, rng: random.Random | None = None) -> bool:
    return (rng or random).random() < SAMPLE[level(stage)]


def record_audit(stage: str, item_id: str, passed: bool, detail: str = "") -> None:
    AUDITS.parent.mkdir(parents=True, exist_ok=True)
    with AUDITS.open("a") as f:
        f.write(json.dumps({"t": datetime.now().isoformat(timespec="seconds"), "stage": stage,
                            "id": item_id, "pass": passed, "detail": detail}) + "\n")
    rate, n = error_rate(stage)
    if n >= 10 and rate > DEMOTE_MIN and level(stage) > 0:
        s = _state()
        s[stage] = 0
        _save(s)
        print(f"[trust] {stage} demoted to 0: error rate {rate:.0%} over last {n}", file=sys.stderr)


def error_rate(stage: str) -> tuple[float, int]:
    if not AUDITS.exists():
        return 0.0, 0
    rows = [json.loads(l) for l in AUDITS.read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r["stage"] == stage][-WINDOW:]
    if not rows:
        return 0.0, 0
    return sum(not r["pass"] for r in rows) / len(rows), len(rows)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    s = _state()
    if cmd == "status":
        for st in STAGES:
            r, n = error_rate(st)
            print(f"{st:12s} level {s.get(st, 0)}  audit error {r:.1%} over last {n}")
    elif cmd == "promote":
        st = sys.argv[2]
        r, n = error_rate(st)
        if n < WINDOW or r > PROMOTE_MAX:
            sys.exit(f"refuse: {st} has {n} audits at {r:.1%} error; need >= {WINDOW} at <= {PROMOTE_MAX:.0%}")
        s[st] = min(3, s.get(st, 0) + 1)
        _save(s)
        print(f"{st} -> level {s[st]}")


if __name__ == "__main__":
    main()
