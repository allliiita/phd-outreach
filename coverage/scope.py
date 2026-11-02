"""The one place that says who is in scope. Everything reads config/targets.yaml through here."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import yaml

from outreach.config import ROOT, canonical_institution
from outreach.enrich import young_title
from outreach.roster import clean_name, faculty_like
from outreach.surnames import asian_tag


@lru_cache
def targets() -> dict:
    return yaml.safe_load((ROOT / "config" / "targets.yaml").read_text())


def schools() -> list[str]:
    """In-scope schools, including institutes that admit PhD students themselves."""
    return [canonical_institution(s) for s in targets()["focus_schools"]]


def via() -> dict[str, str]:
    """Institute -> the in-scope school whose census its PIs are counted under."""
    out = {}
    for i in targets().get("institutes_this_round", []):
        v = i.get("via", "")
        if v in targets()["focus_schools"]:
            out[i["name"]] = v
    return out


def name_key(name: str) -> tuple[str, str]:
    """Order-free (first, last) key: 'Sun, Wen' == 'Wen Sun' == 'Wen  Sun, PhD'."""
    n = unicodedata.normalize("NFKD", clean_name(name)).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", n)
    toks = [t for t in re.split(r"[^a-z]+", n) if len(t) > 1]
    return tuple(sorted({toks[0], toks[-1]})) if toks else ("", "")


def heritage_ok(name: str) -> bool:
    want = targets().get("heritage")
    return not want or asian_tag(clean_name(name)) == want


def gate(row: dict) -> str | None:
    """First scope rule a roster row fails, or None if the person is in scope."""
    if not faculty_like(row):
        return "not faculty"
    t = row.get("title_on_roster") or ""
    if t and not young_title(t):
        return "not young"
    if not heritage_ok(row.get("name") or ""):
        return "heritage"
    return None
