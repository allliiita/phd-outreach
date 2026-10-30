"""Record schema. Layer 1 of the trust pyramid: wrong records should be unrepresentable.

Every factual field carries the URL it came from and the verbatim text that supports it.
A field without evidence cannot be constructed.
"""
from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class PositionClass(str, Enum):
    incoming_assistant = "incoming_assistant"
    assistant = "assistant"
    associate = "associate"
    full = "full"
    institute_pi = "institute_pi"          # independent PI at a research institute
    research_faculty = "research_faculty"  # research professor / research scientist (may or may not advise)
    teaching = "teaching"                  # lecturer / teaching professor: excluded from A tier
    emeritus = "emeritus"                  # excluded from outreach
    staff_scientist = "staff_scientist"    # institute non-PI: excluded from outreach
    other = "other"


class Recruiting(str, Enum):
    confirmed = "Confirmed"
    possible = "Possible"
    unknown = "Unknown"
    not_recruiting = "Not recruiting"


class Relevance(str, Enum):
    yes = "yes"
    borderline = "borderline"   # human decides
    no = "no"


class Evidence(BaseModel):
    source_url: HttpUrl
    quote: str = Field(min_length=1, description="verbatim text copied from the page")
    checked_on: date


class Sourced(BaseModel):
    value: str
    evidence: Evidence


class Paper(BaseModel):
    title: str
    year: int
    url: HttpUrl
    source: str = Field(description="openalex | semantic_scholar | dblp | homepage")

    @field_validator("year")
    @classmethod
    def recent(cls, y: int) -> int:
        if y < date.today().year - 3:
            raise ValueError(f"paper year {y} is older than 3 years")
        return y


class Email(BaseModel):
    value: str
    evidence: Evidence

    @model_validator(mode="after")
    def email_in_quote(self) -> "Email":
        if not EMAIL_RE.match(self.value):
            raise ValueError(f"malformed email {self.value!r}")
        if not email_appears_in(self.value, self.evidence.quote):
            raise ValueError(f"email {self.value!r} does not appear in its evidence quote")
        return self


def deobfuscate(text: str) -> str:
    t = text
    t = re.sub(r"\s*[\[\(\{<]\s*(?:at|through|@)\s*[\]\)\}>]\s*", "@", t, flags=re.I)   # [at] (at) (through)
    t = re.sub(r"\s+at\s+(?=[A-Za-z0-9\-]+\s*(?:[\[\(\{]\s*dot|\.|dot\s))", "@", t, flags=re.I)
    t = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", t, flags=re.I)
    t = re.sub(r"\s+dot\s+", ".", t, flags=re.I)
    t = re.sub(r"[.\-_]?(?:no\.?spam|nospam|remove\.?this|spamfree)\b", "", t, flags=re.I)  # jinglei@andrew.cmu.edu.no.spam
    return t


def email_appears_in(email: str, text: str) -> bool:
    e = email.lower()
    if e in text.lower():
        return True
    return e in deobfuscate(text).lower().replace(" ", "")


class Recruit(BaseModel):
    status: Recruiting
    evidence: Optional[Evidence] = None

    @model_validator(mode="after")
    def needs_evidence(self) -> "Recruit":
        if self.status in (Recruiting.confirmed, Recruiting.not_recruiting) and self.evidence is None:
            raise ValueError(f"recruiting={self.status.value} requires a verbatim quote")
        return self


class InstituteInfo(BaseModel):
    independent_pi: bool
    university_appointment: Optional[Sourced] = None  # e.g. "Associate Professor, MIT Biology"
    phd_path: Optional[str] = None                     # e.g. "via Harvard BBS / MIT Biology"


class Person(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9\-]+$")
    tier: str = Field(pattern=r"^[AB]$")
    name: str
    institution: str
    departments: list[str] = Field(min_length=1)
    position: Sourced                       # title as written on the page
    position_class: PositionClass
    start_year: Optional[Sourced] = None
    email: Optional[Email] = None           # None => "Not listed". Never guessed.
    homepage: Optional[HttpUrl] = None
    lab_website: Optional[HttpUrl] = None
    google_scholar: Optional[HttpUrl] = None
    keywords: list[str] = Field(default_factory=list)
    keywords_evidence: Optional[Evidence] = None
    recent_papers: list[Paper] = Field(default_factory=list)
    recruiting: Recruit = Recruit(status=Recruiting.unknown)
    relevance: Relevance
    relevance_reason: str
    institute: Optional[InstituteInfo] = None
    notes: str = ""                         # profile facts useful for personalisation, each with a url

    @model_validator(mode="after")
    def tier_requirements(self) -> "Person":
        if self.google_scholar and "scholar.google" not in str(self.google_scholar):
            raise ValueError("google_scholar is not a scholar.google.* URL")
        if self.tier == "A":
            if not (3 <= len(self.keywords) <= 8):
                raise ValueError("A tier needs 3-8 keywords")
            if self.keywords_evidence is None:
                raise ValueError("A tier keywords need evidence")
            if not (1 <= len(self.recent_papers) <= 3):
                raise ValueError("A tier needs 1-3 recent papers")
            if self.position_class in (PositionClass.teaching, PositionClass.emeritus, PositionClass.staff_scientist):
                raise ValueError(f"{self.position_class.value} cannot be A tier")
        return self

    @property
    def early_career(self) -> bool:
        if self.position_class in (PositionClass.incoming_assistant, PositionClass.assistant):
            return True
        if self.start_year and self.position_class in (PositionClass.associate, PositionClass.institute_pi):
            try:
                return int(self.start_year.value[:4]) >= date.today().year - 6
            except ValueError:
                return False
        return False
