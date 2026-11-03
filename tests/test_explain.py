import json
from argparse import Namespace

import pytest

from coverage import explain, scope

S = "Cornell University"


def args(**kw):
    d = dict(school=S, name="Wen Sun", reason="moved_institution", evidence="https://e.example/p", quote="", unit=None, to=None,
             title=None, note="")
    d.update(kw)
    return Namespace(**d)


PAGE = "<html><body><p>Wen  Sun is now a Research   Scientist at Databricks.</p></body></html>"


def fetch(url):
    return PAGE


def test_quote_required_and_must_be_on_page():
    assert explain.build(args(to="Databricks"), fetch)[1] == "--quote is required"
    r, err = explain.build(args(to="Databricks", quote="Wen Sun is now a research scientist at databricks"), fetch)
    assert err is None and r["quote"] and r["fetched"]
    assert "not found" in explain.build(args(to="Databricks", quote="Wen Sun is a professor at Databricks"), fetch)[1]


def test_moved_quote_must_name_new_institution():
    assert "new institution" in explain.build(args(to="Google", quote="Wen Sun is now a Research Scientist"), fetch)[1]
    assert explain.build(args(quote="Wen Sun is now a Research Scientist"), fetch)[1] == "moved_institution needs --to"


@pytest.mark.parametrize("url", ["https://api.nsf.gov/services/v1/awards/1.json", "https://reporter.nih.gov/project-details/1"])
def test_unit_exclusion_refuses_api_evidence(url):
    a = args(reason="out_of_scope_unit", evidence=url, unit="Physics", quote="Department of Physics")
    assert "carry no department" in explain.build(a, lambda u: "Department of Physics")[1]


def test_unit_must_be_in_quote():
    a = args(reason="clinical_unit", unit="Radiology", quote="Wen Sun, Department of Surgery")
    assert "unit" in explain.build(a, lambda u: "Wen Sun, Department of Surgery")[1]
    a = args(reason="clinical_unit", unit="Surgery", quote="Wen Sun, Department of Surgery")
    assert explain.build(a, lambda u: "Wen Sun, Department of Surgery")[1] is None


def test_title_must_be_in_quote():
    a = args(reason="senior_title", title="Professor", quote="Wen Sun, Lecturer")
    assert "title" in explain.build(a, lambda u: "Wen Sun, Lecturer")[1]


def proj(fy, code="K99", org="CORNELL UNIVERSITY", first="Wen", last="Sun"):
    return {"fiscal_year": fy, "project_num": f"5{code}GM1", "project_title": "Deep learning of cells", "project_detail_url": "https://reporter.nih.gov/project-details/1",
            "organization": {"org_name": org}, "principal_investigators": [{"first_name": first, "last_name": last}]}


def reporter(k99, r00=()):
    return lambda last, codes: list(k99 if codes == ["K99"] else r00)


def k99(rep):
    a = args(reason="postdoc_pre_independent", evidence="https://reporter.nih.gov/project-details/1", quote="Deep learning of cells")
    return explain.build(a, None, rep)


def test_k99_rule(monkeypatch):
    monkeypatch.setattr(explain, "current_fy", lambda today=None: 2027)
    r, err = k99(reporter([proj(2026)]))
    assert err is None and r["fy"] == 2026
    assert "fiscal year" in k99(reporter([proj(2024)]))[1]                    # stale K99
    assert "R00" in k99(reporter([proj(2026)], [proj(2025, "R00")]))[1]       # already independent
    assert "no K99" in k99(reporter([proj(2026, first="Other")]))[1]          # other PI
    assert "no K99" in k99(reporter([proj(2026, org="STANFORD UNIVERSITY")]))[1]


def test_alias_needs_ledger_name(tmp_path, monkeypatch):
    (tmp_path / "coverage").mkdir()
    (tmp_path / "coverage" / "people.jsonl").write_text(json.dumps({"school": S, "key": list(scope.name_key("Alan Liu"))}) + "\n")
    monkeypatch.setattr(explain, "DATA", tmp_path)
    ok = args(name="Zaoxing Liu", reason="alias_of_ledger", note="same as Alan Liu")
    assert explain.build(ok)[1] is None
    assert explain.build(args(name="Zaoxing Liu", reason="alias_of_ledger", note="same as Nobody Here"))[1]
    assert explain.build(args(name="Zaoxing Liu", reason="alias_of_ledger", note="seems the same"))[1]


def test_validate_flags_legacy_rows(tmp_path, monkeypatch, capsys):
    (tmp_path / "coverage").mkdir()
    (tmp_path / "coverage" / "explained.jsonl").write_text(json.dumps({"school": S, "name": "Wen Sun", "reason": "moved_institution",
                                                                      "evidence_url": "https://e.example/p"}) + "\n")
    monkeypatch.setattr(explain, "DATA", tmp_path)
    assert explain.main(["--validate"]) == 1
    assert "UNPROVEN" in capsys.readouterr().out
