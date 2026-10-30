"""Unit tests for the deterministic layer. Run: python -m pytest -q"""
import copy

import pytest
from pydantic import ValidationError

from outreach.emailcheck import check_one
from outreach.schema import Person, deobfuscate, email_appears_in
from outreach.validate import check

EV = {"source_url": "https://www.cmu.edu/x", "quote": "Assistant Professor", "checked_on": "2026-10-30"}
BASE = {
    "id": "jane-doe-cmu", "tier": "A", "name": "Jane Doe", "institution": "Carnegie Mellon University",
    "departments": ["Statistics & Data Science"],
    "position": {"value": "Assistant Professor", "evidence": EV}, "position_class": "assistant",
    "email": {"value": "jdoe@andrew.cmu.edu", "evidence": {**EV, "quote": "Email: jdoe [at] andrew [dot] cmu [dot] edu"}},
    "keywords": ["conformal prediction", "causal inference", "single-cell genomics"],
    "keywords_evidence": {**EV, "quote": "I work on conformal prediction and causal inference."},
    "recent_papers": [{"title": "A Paper About Conformal Prediction", "year": 2025, "url": "https://arxiv.org/abs/1", "source": "openalex"}],
    "relevance": "yes", "relevance_reason": "conformal prediction",
}


def test_valid_record():
    Person.model_validate(BASE)
    assert check([BASE]) == []


def test_obfuscated_email():
    assert email_appears_in("jdoe@andrew.cmu.edu", "jdoe [at] andrew [dot] cmu [dot] edu")
    assert deobfuscate("a (at) b (dot) edu") == "a@b.edu"
    # pilot lessons: CMU profile pages and homepages
    assert email_appears_in("ek3@andrew.cmu.edu", "Email: ek3(through)andrew.cmu.edu")
    assert email_appears_in("annlee@stat.cmu.edu", "annlee AT stat DOT cmu DOT edu")
    assert email_appears_in("davidch@andrew.cmu.edu", "davidch at andrew.cmu.edu")
    assert email_appears_in("jinglei@andrew.cmu.edu", "jinglei [at] andrew.cmu.edu.no.spam")


def test_email_not_in_quote_rejected():
    r = copy.deepcopy(BASE)
    r["email"]["evidence"]["quote"] = "Contact the department office"
    with pytest.raises(ValidationError):
        Person.model_validate(r)


def test_wrong_domain_flagged():
    r = copy.deepcopy(BASE)
    r["email"] = {"value": "jdoe@gmail.com", "evidence": {**EV, "quote": "jdoe@gmail.com"}}
    assert any("domain" in m for _, m in check([r]))


def test_old_paper_rejected():
    r = copy.deepcopy(BASE)
    r["recent_papers"][0]["year"] = 2019
    with pytest.raises(ValidationError):
        Person.model_validate(r)


def test_confirmed_recruiting_needs_quote():
    r = copy.deepcopy(BASE)
    r["recruiting"] = {"status": "Confirmed", "evidence": None}
    with pytest.raises(ValidationError):
        Person.model_validate(r)


def test_emeritus_cannot_be_A():
    r = copy.deepcopy(BASE)
    r["position_class"] = "emeritus"
    with pytest.raises(ValidationError):
        Person.model_validate(r)


def test_duplicates_flagged():
    r2 = copy.deepcopy(BASE)
    r2["id"] = "jane-doe-cmu-2"
    r2["name"] = "Dr. Jane Q. Doe"
    msgs = [m for _, m in check([BASE, r2])]
    assert any("duplicate person" in m for m in msgs)
    assert any("shared by" in m for m in msgs)


def test_email_check():
    p = Person.model_validate(BASE)
    good = {"id": p.id, "to": "jdoe@andrew.cmu.edu", "subject": "Prospective PhD student (Fall 2027)",
            "body": "Dear Professor Doe,\n\n" + "I read \"A Paper About Conformal Prediction\" with interest. " + "word " * 140 + "\nFall 2027\nLindsey Ma",
            "claims": [{"field": "recent_papers"}]}
    assert check_one(good, p) == []
    bad = dict(good, to="jane@cmu.edu", body=good["body"].replace("Doe", "Smith", 1) + " groundbreaking, recommendation letter")
    errs = check_one(bad, p)
    assert any("differs" in e for e in errs) and any("surname" in e for e in errs) and any("banned" in e for e in errs)
