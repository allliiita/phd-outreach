from argparse import Namespace

import pytest

from coverage import explain

S = "Cornell University"


def args(**kw):
    d = dict(school=S, name="Wen Sun", reason="moved_institution", evidence="https://e.example/p", quote="", unit=None, to=None,
             title=None, note="")
    d.update(kw)
    return Namespace(**d)


def build(a, text):
    return explain.build(a, lambda u: text)


def test_surname_required_senior_and_moved():
    t = "Faculty directory | Professor | University of Wisconsin"
    assert "surname" in build(args(reason="senior_title", title="Professor", quote="Professor"), t)[1]
    assert "surname" in build(args(to="Wisconsin", quote="University of Wisconsin"), t)[1]
    assert "surname" in build(args(reason="not_phd_advising_title", title="Lecturer", quote="Lecturer"), "Lecturer")[1]
    assert build(args(reason="senior_title", title="Professor", quote="Wen Sun, Professor"), "Wen Sun, Professor")[1] is None


def test_zero_width_and_nbsp_normalized():
    page = "Wen​ Sun, Professor of CS"
    assert build(args(reason="senior_title", title="Professor", quote="Wen Sun, Professor of CS"), page)[1] is None
    assert explain.contains("Wen​Sun", "wensun")


@pytest.mark.parametrize("to,quote", [("MIT", "Wen Sun, MIT"), ("UC Berkeley", "Wen Sun, University of California Berkeley"),
                                      ("Massachusetts Institute of Technology", "Wen Sun, MIT"),
                                      ("Univ. of California - Berkeley", "Wen Sun, UC Berkeley")])
def test_to_accepts_aliases(to, quote):
    assert build(args(to=to, quote=quote), quote)[1] is None


def test_alias_whole_word_and_wrong_school():
    assert "new institution" in build(args(to="MIT", quote="Wen Sun, summit"), "Wen Sun, summit")[1]
    assert "new institution" in build(args(to="MIT", quote="Wen Sun, Stanford"), "Wen Sun, Stanford")[1]


@pytest.mark.parametrize("unit", ["Electrical and Computer Engineering", "Department of Statistics", "Data Science Institute",
                                  "Applied Mathematics", "School of Information", "Linguistics", "Operations Research",
                                  "Computational Cognitive Science"])
def test_out_of_scope_refused_for_core_units(unit):
    a = args(reason="out_of_scope_unit", unit=unit, quote=f"Wen Sun, {unit}")
    assert "always in scope" in build(a, f"Wen Sun, {unit}")[1]


def test_out_of_scope_ok_for_physics():
    a = args(reason="out_of_scope_unit", unit="Physics", quote="Wen Sun, Physics")
    assert build(a, "Wen Sun, Physics")[1] is None


def proj(code, org, fy=2026, first="Furong", last="Huang"):
    return {"fiscal_year": fy, "project_num": f"1{code}CA1", "project_title": "Programmable RNA engineering",
            "project_detail_url": "https://reporter.nih.gov/project-details/1", "organization": {"org_name": org},
            "principal_investigators": [{"first_name": first, "last_name": last}]}


def test_k99_queries_real_last_name_and_r00_hint(monkeypatch):
    seen = []

    def rep(last, codes):
        seen.append(last)
        return [proj("K99", "DUKE UNIVERSITY")] if codes == ["K99"] else []
    monkeypatch.setattr(explain, "current_fy", lambda today=None: 2027)
    fy, _, err = explain.check_k99("Duke University", "Furong Huang", "Programmable RNA", rep)
    assert err is None and set(seen) == {"Huang"}
    rep2 = lambda last, codes: [proj("K99", "DUKE UNIVERSITY")] if codes == ["K99"] else [proj("R00", "CORNELL UNIVERSITY", 2027)]
    err = explain.check_k99("Duke University", "Furong Huang", "Programmable RNA", rep2)[2]
    assert "CORNELL UNIVERSITY" in err and "add_person" in err
    rep3 = lambda last, codes: [proj("K99", "DUKE UNIVERSITY")] if codes == ["K99"] else [proj("R00", "UNIVERSITY OF SOMEWHERE ELSE", 2027)]
    assert "moved_institution" in explain.check_k99("Duke University", "Furong Huang", "Programmable RNA", rep3)[2]
