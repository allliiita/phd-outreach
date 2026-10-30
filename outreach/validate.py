"""Layer 2 of the trust pyramid: deterministic checks. No LLM judgement here.

Usage: python -m outreach.validate data/people.jsonl [--snapshots data/snapshots]
Exit code 1 if any record fails. Prints one line per problem.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from .schema import Person, PositionClass, email_appears_in
from .config import institution_domains

BANNED_KEYWORDS = {"machine learning", "ai", "artificial intelligence", "statistics", "data science", "research"}


def norm_name(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\b(dr|prof|professor|phd)\b\.?", "", n)
    n = re.sub(r"\b[a-z]\.\s*", "", n)          # drop middle initials
    return " ".join(re.sub(r"[^a-z ]", " ", n).split())


def snapshot_text(snapshots: Path | None, url: str) -> str | None:
    """Raw HTML/text saved by fetch.py at fetch time (deterministic evidence)."""
    if snapshots is None:
        return None
    from .fetch import snapshot_path
    p = snapshot_path(snapshots, url)
    return p.read_text(errors="ignore") if p.exists() else None


def check(people_raw: list[dict], snapshots: Path | None = None) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    parsed: list[Person] = []
    for raw in people_raw:
        pid = raw.get("id", "?")
        try:
            parsed.append(Person.model_validate(raw))
        except ValidationError as e:
            for err in e.errors():
                problems.append((pid, f"schema {'.'.join(map(str, err['loc']))}: {err['msg']}"))

    seen_id: dict[str, int] = defaultdict(int)
    seen_name: dict[tuple[str, str], list[str]] = defaultdict(list)
    seen_email: dict[str, list[str]] = defaultdict(list)

    for p in parsed:
        seen_id[p.id] += 1
        seen_name[(norm_name(p.name), p.institution.lower())].append(p.id)

        if p.email:
            em = p.email.value.lower()
            seen_email[em].append(p.id)
            domains = institution_domains(p.institution)
            dom = em.split("@", 1)[1]
            if domains and not any(dom == d or dom.endswith("." + d) for d in domains):
                problems.append((p.id, f"WARN email domain {dom} not in official domains {domains} (personal address from own homepage?)"))
            # the email must be on the actual saved page, not just in the agent's quote
            snap = snapshot_text(snapshots, str(p.email.evidence.source_url))
            if snap is not None and not email_appears_in(p.email.value, snap):
                problems.append((p.id, "email not found in saved snapshot of its source page"))
            # name plausibility: a name token (>=3 chars) or the initials in the local part, or the name in the quote.
            # (lesson from pilot: davidch@, joel@, isabella@ are real first-name addresses)
            toks = [t for t in norm_name(p.name).split() if len(t) >= 3]
            local = em.split("@")[0]
            initials = "".join(t[0] for t in norm_name(p.name).split())
            quote = p.email.evidence.quote.lower()
            uni = re.fullmatch(r"([a-z]{2,4})\d{2,5}", local)   # Columbia-style UNI: initials + digits
            uni_ok = bool(uni) and uni.group(1)[0] == initials[:1] and uni.group(1)[-1] == initials[-1:]
            if uni and not uni_ok:
                problems.append((p.id, f"email {em}: UNI letters {uni.group(1)!r} do not match initials {initials!r} (directory error?)"))
            elif not uni and toks and not any(t in local or t in quote or (len(local) >= 3 and t.startswith(local)) for t in toks) \
                    and not local.startswith(initials[:2]):
                problems.append((p.id, f"email {em}: no part of the name in address or quote (wrong person?)"))

        for fld, ev in (("position", p.position.evidence), ("keywords", p.keywords_evidence)):
            if ev is None:
                continue
            snap = snapshot_text(snapshots, str(ev.source_url))
            if snap is not None:
                from .fetch import visible_text
                q = " ".join(ev.quote.split()).lower()[:120]
                if q not in " ".join(snap.split()).lower() and q not in visible_text(snap).lower():
                    problems.append((p.id, f"{fld} quote not found in saved snapshot"))

        if p.tier == "A":
            vague = [k for k in p.keywords if k.strip().lower() in BANNED_KEYWORDS]
            if vague:
                problems.append((p.id, f"keywords too generic: {vague}"))
            titles = [x.title.strip().lower() for x in p.recent_papers]
            if len(set(titles)) != len(titles):
                problems.append((p.id, "duplicate paper titles"))

        title = p.position.value.lower()
        expect = {
            PositionClass.emeritus: "emerit",
            PositionClass.incoming_assistant: "assistant",
            PositionClass.assistant: "assistant",
            PositionClass.associate: "associate",
        }.get(p.position_class)
        if expect and expect not in title and "incoming" not in title:
            problems.append((p.id, f"position_class={p.position_class.value} but title is '{p.position.value}'"))
        if "emerit" in title and p.position_class != PositionClass.emeritus:
            problems.append((p.id, "title says emeritus but class is not emeritus"))
        if p.institute and not p.institute.independent_pi and p.tier == "A":
            problems.append((p.id, "non-independent institute researcher marked tier A"))

    for k, n in seen_id.items():
        if n > 1:
            problems.append((k, f"duplicate id x{n}"))
    for (name, inst), ids in seen_name.items():
        if len(ids) > 1:
            problems.append((ids[0], f"possible duplicate person {name} @ {inst}: {ids}"))
    for em, ids in seen_email.items():
        if len(ids) > 1:
            problems.append((ids[0], f"email {em} shared by {ids}"))
    return problems


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('{"_'):
            rows.append(json.loads(line))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("people", type=Path)
    ap.add_argument("--snapshots", type=Path, default=None)
    a = ap.parse_args()
    rows = load_jsonl(a.people)
    probs = check(rows, a.snapshots)
    for pid, msg in probs:
        print(f"{pid}\t{msg}")
    bad = {pid for pid, m in probs if not m.startswith("WARN")}
    print(f"# {len(rows)} records, {len(rows) - len(bad & {r.get('id') for r in rows})} clean, {len(bad)} with problems", file=sys.stderr)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
