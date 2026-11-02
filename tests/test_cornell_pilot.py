"""Regression tests found by the Cornell pilot (2026-11-02). Each fails on the pre-fix code."""
import json

from coverage import check, scope
from outreach.roster import clean_name


def test_unit_names_with_semicolons_in_parentheses_stay_one_unit():
    # "Robotics (field; members listed in CS/ECE/MAE)" was split into two phantom units
    assert check.split_units("Robotics (field; members listed in CS/ECE/MAE)") == ["Robotics (field; members listed in CS/ECE/MAE)"]
    assert check.split_units("Computer Science; Information Science; Statistics & Data Science") == [
        "Computer Science", "Information Science", "Statistics & Data Science"]
    assert check.split_units("A (x; y); B") == ["A (x; y)", "B"]


def test_parenthesised_unit_matches_its_grid_row(tmp_path, monkeypatch):
    name = "Robotics (field; members listed in CS/ECE/MAE)"
    (tmp_path / "grid").mkdir()
    (tmp_path / "grid" / "duke.units.jsonl").write_text(json.dumps({"unit": "R", "decision": "covered", "grid_unit": name}) + "\n")
    (tmp_path / "grid" / "duke.jsonl").write_text(json.dumps({"unit": name, "status": "alt", "alt_source": "u"}) + "\n")
    monkeypatch.setattr(check, "DATA", tmp_path)
    monkeypatch.setattr(check, "SLUG", {"Duke University": "duke"})
    assert check.units("Duke University") == []


def test_first_names_that_look_like_degrees_are_kept():
    # ORIE "Meng Qi" became "Qi" (M.Eng prefix rule); "Md" (Mohammad) is a first name too
    assert clean_name("Meng Qi") == "Meng Qi"
    assert clean_name("Md Rahman") == "Md Rahman"
    assert scope.name_key("Meng Qi") == ("meng", "qi")
    assert clean_name("Dr. Wen Li") == "Wen Li"
    assert clean_name("Prof. Wen Li") == "Wen Li"
    assert clean_name("Wen Li, PhD") == "Wen Li"


def test_nsf_truncated_pi_name_matches_ledger_person(tmp_path, monkeypatch):
    # NSF cuts PI names at 29 chars: "Cristian Danescu-Niculescu-Mi" is Cristian Danescu-Niculescu-Mizil (ledger row exists)
    ledger = [{"school": "Cornell University", "key": list(scope.name_key("Cristian Danescu-Niculescu-Mizil"))}]
    (tmp_path / "probes").mkdir()
    (tmp_path / "probes" / "nsf_career.jsonl").write_text(json.dumps(
        {"name": "Cristian Danescu-Niculescu-Mi", "school": "Cornell University", "year": 2018, "source_url": "u"}) + "\n")
    (tmp_path / "coverage").mkdir()
    monkeypatch.setattr(check, "DATA", tmp_path)
    assert check.recall(ledger) == {}
    # a short name is never prefix-matched
    (tmp_path / "probes" / "nsf_career.jsonl").write_text(json.dumps(
        {"name": "Wen Su", "school": "Cornell University", "year": 2018, "source_url": "u"}) + "\n")
    ledger = [{"school": "Cornell University", "key": list(scope.name_key("Wen Sun"))}]
    assert len(check.recall(ledger)) == 1
