import json

import pytest

from coverage import check, scope


@pytest.mark.parametrize("a,b", [("Sun, Wen", "Wen Sun"), ("Wen  Sun, PhD", "Wen Sun"), ("Wen Sun", "Wen Sun"),
                                 ('Qingrong "Jackie" Wu PhD', "Qingrong Wu"), ("Xi Chen M.Sc", "Xi Chen"),
                                 ("Li Wang Jr.", "Li Wang"), ("Ting Wang DPhil", "Ting Wang"), ("Wu, Qingrong", "Qingrong Wu")])
def test_name_key_order_and_credentials(a, b):
    assert scope.name_key(a) == scope.name_key(b)


def test_credential_is_not_the_surname():
    assert "phd" not in scope.name_key('Qingrong "Jackie" Wu PhD')
    assert scope.name_key("Ying Ma") == ("ma", "ying")   # Ma is a surname, not a degree


def test_heritage_ok_with_credentials_and_nickname():
    assert scope.heritage_ok('Qingrong "Jackie" Wu PhD')
    assert scope.heritage_ok("John Smith") is False


def row(**kw):
    return {"name": "Wen Li", "title_on_roster": "Assistant Professor", "quote": "Wen Li Assistant Professor", **kw}


def test_gate():
    assert scope.gate(row()) is None
    assert scope.gate(row(title_on_roster="")) is None                        # title unknown: stays in, verified later
    assert scope.gate(row(title_on_roster="Professor")) == "not young"
    assert scope.gate(row(name="John Smith")) == "heritage"
    assert scope.gate(row(title_on_roster="PhD Student", quote="Wen Li PhD Student")) is not None


SCHOOL = "Duke University"


def fixture(tmp_path, monkeypatch, status):
    d = tmp_path
    for sub in ("grid", "coverage", "probes"):
        (d / sub).mkdir(exist_ok=True)
    (d / "grid" / "duke.units.jsonl").write_text(json.dumps({"unit": "CS", "decision": "covered", "grid_unit": "Computer Science"}) + "\n")
    (d / "grid" / "duke.jsonl").write_text(json.dumps({"unit": "Computer Science", "status": status}) + "\n")
    (d / "coverage" / "people.jsonl").write_text(json.dumps(
        {"school": SCHOOL, "name": "Wen Li", "key": list(scope.name_key("Wen Li")), "in_scope": True, "outcome": "listed",
         "title": "", "units": []}) + "\n")
    (d / "probes" / "csrankings.jsonl").write_text(json.dumps(
        {"name": "Li, Wen", "school": SCHOOL, "year": 2015, "source_url": "u", "detail": {}}) + "\n")
    monkeypatch.setattr(check, "DATA", d)
    monkeypatch.setattr(check, "SLUG", {SCHOOL: "duke"})
    monkeypatch.setattr(check, "unverified", lambda ledger: [])
    monkeypatch.setattr(scope, "schools", lambda: [SCHOOL])


def test_check_exit_codes(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, "done")
    assert check.main([]) == 0
    fixture(tmp_path, monkeypatch, "blocked")          # a blocked BIG unit fails the build
    assert check.main([]) == 1


def test_probe_hit_without_ledger_row_fails_until_explained(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, "done")
    with (tmp_path / "probes" / "csrankings.jsonl").open("a") as f:
        f.write(json.dumps({"name": "Wen Sun", "school": SCHOOL, "year": 2014, "source_url": "u", "detail": {}}) + "\n")
    assert check.main([]) == 1
    (tmp_path / "coverage" / "explained.jsonl").write_text(json.dumps({"school": SCHOOL, "name": "Sun, Wen", "reason": "moved"}) + "\n")
    assert check.main([]) == 0


def test_open_funnel_and_missing_census_fail(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, "done")
    (tmp_path / "coverage" / "people.jsonl").write_text(json.dumps(
        {"school": SCHOOL, "name": "Wen Li", "key": list(scope.name_key("Wen Li")), "in_scope": True, "outcome": "open",
         "title": "", "units": []}) + "\n")
    assert check.main([]) == 1
    fixture(tmp_path, monkeypatch, "done")
    (tmp_path / "grid" / "duke.units.jsonl").unlink()
    assert check.main([]) == 1
