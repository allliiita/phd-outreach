"""The one place that says who is in scope. Everything reads config/targets.yaml through here."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
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
            out[canonical_institution(i["name"])] = canonical_institution(v)
    return out


# Credentials / generational suffixes that roster.clean_name misses ("Xi Chen M.Sc", "Li Wang Jr.", "Ting Wang DPhil").
# Case-sensitive on purpose: "Ma"/"Ms" are surnames, "MA"/"MS" are degrees. A comma before the token makes it unambiguous.
_CRED = r"Jr|Sr|II|III|IV|PhD|DPhil|MPhil|MSc|BSc|MBBS|MBChB|MD|MPH|MS|MA|ScD|DrPH|DVM|PharmD|MBA|MSPH|MSHP|MSCE|MEng|FACS|FACP|FAHA|FACMI|RN|NP"
_CRED_DOTTED = r"(?:[A-Za-z]\.){2,}|[A-Z][a-z]?\.[A-Za-z][a-z]?\.?|Jr\.|Sr\.|Ph\.?D\.?|Sc\.?D\.?"
_TAIL = re.compile(rf"(?:\s*,\s*|\s+)(?:{_CRED_DOTTED}|{_CRED})\.?$")


def bare_name(name: str) -> str:
    """Name without degrees, generational suffixes and nicknames: 'Qingrong "Jackie" Wu PhD' -> 'Qingrong Wu'.
    Root fix for credential suffixes becoming the 'surname' (UCSF rows were lost to this)."""
    n = clean_name(name)
    for _ in range(6):
        m = _TAIL.sub("", n).strip(" ,")
        m = clean_name(m) if " " in m else m
        if m == n or " " not in m:
            break
        n = m
    n = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", n)).strip()
    m = re.fullmatch(r"([^,]+),\s*([^,]+)", n)   # "Wu, Qingrong" -> "Qingrong Wu"
    return f"{m.group(2)} {m.group(1)}" if m else n


def name_key(name: str) -> tuple[str, str]:
    """Order-free (first, last) key: 'Sun, Wen' == 'Wen Sun' == 'Wen  Sun, PhD'."""
    n = unicodedata.normalize("NFKD", bare_name(name)).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", n)
    toks = [t for t in re.split(r"[^a-z]+", n) if len(t) > 1]
    return tuple(sorted({toks[0], toks[-1]})) if toks else ("", "")


def heritage_ok(name: str) -> bool:
    want = targets().get("heritage")
    return not want or asian_tag(bare_name(name)) == want


# Copied from outreach/batch1.py (which may be deleted). school -> slug of data/grid/<slug>.jsonl
SLUG = {"Boston University": "boston-university", "Duke University": "duke", "University of South Florida": "usf",
        "University of California San Francisco": "ucsf", "Cold Spring Harbor Laboratory": "cshl",
        "Icahn School of Medicine at Mount Sinai": "mount-sinai", "Washington University in St. Louis": "washu",
        "University of Virginia": "uva", "University of Michigan": "umich", "University of Pennsylvania": "upenn",
        "Johns Hopkins University": "jhu", "University of Central Florida": "ucf", "Cornell University": "cornell",
        "Rockefeller University": "rockefeller", "University of Washington": "uw",
        "University of California San Diego": "ucsd", "University of Maryland": "umd",
        "Georgia Institute of Technology": "gatech", "University of California Irvine": "uci",
        "University of California Santa Cruz": "ucsc", "University of Massachusetts Amherst": "umass",
        "University of California Santa Barbara": "ucsb", "New York University": "nyu"}

DATA = ROOT / "data"


def jl(p) -> list[dict]:
    p = Path(p)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def school_of(institution: str) -> str | None:
    """In-scope school for a roster institution string (institutes count under their via-school), else None."""
    c = canonical_institution(institution or "")
    if c in schools():
        return c
    return via().get(c)


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
