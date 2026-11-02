"""Loads config/institutions.yaml (schools, institutes, departments, official email domains)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@lru_cache
def institutions() -> dict:
    return yaml.safe_load((ROOT / "config" / "institutions.yaml").read_text())


def _k(s: str) -> str:
    return " ".join(s.lower().replace(",", " ").split())


def canonical_institution(name: str) -> str:
    """Official name from config/institutions.yaml ('University of California, Irvine' -> '... Irvine')."""
    for inst in institutions()["institutions"]:
        if _k(name) in [_k(inst["name"])] + [_k(a) for a in inst.get("aliases", [])]:
            return inst["name"]
    return name


def institution_domains(name: str) -> list[str]:
    for inst in institutions()["institutions"]:
        if inst["name"] == canonical_institution(name):
            return inst.get("email_domains", [])
    return []


@lru_cache
def profile() -> dict:
    return yaml.safe_load((ROOT / "config" / "applicant.yaml").read_text())
