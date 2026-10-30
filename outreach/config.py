"""Loads config/institutions.yaml (schools, institutes, departments, official email domains)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@lru_cache
def institutions() -> dict:
    return yaml.safe_load((ROOT / "config" / "institutions.yaml").read_text())


def institution_domains(name: str) -> list[str]:
    for inst in institutions()["institutions"]:
        if inst["name"].lower() == name.lower() or name.lower() in [a.lower() for a in inst.get("aliases", [])]:
            return inst.get("email_domains", [])
    return []


@lru_cache
def profile() -> dict:
    return yaml.safe_load((ROOT / "config" / "applicant.yaml").read_text())
