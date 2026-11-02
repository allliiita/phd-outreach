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


def test_ledger_ignores_probe_sourced_rosters(tmp_path, monkeypatch):
    # Wen Sun entered the ledger through a CSRankings-built roster though he left Cornell: probes are leads, never rosters
    from coverage import ledger
    (tmp_path / "roster").mkdir()
    base = {"institution": "Cornell University", "title_on_roster": "Assistant Professor", "filter": "all"}
    rows = {"cornell-x.jsonl": {**base, "name": "Real Person", "department": "CS", "roster_url": "https://www.cs.cornell.edu/people"},
            "cornell-probe.jsonl": {**base, "name": "Gone Person", "department": "CS", "roster_url": "https://csrankings.org/"},
            "cornell-probe2.jsonl": {**base, "name": "Nsf Person", "department": "CS",
                                     "roster_url": "https://api.nsf.gov/services/v1/awards/1.json"}}
    for f, r in rows.items():
        (tmp_path / "roster" / f).write_text(json.dumps(r) + "\n")
    monkeypatch.setattr(ledger, "DATA", tmp_path)
    names = {p["name"] for p in ledger.build()}
    assert "Real Person" in names and "Gone Person" not in names and "Nsf Person" not in names


def test_titles_reject_past_phrasing():
    from coverage.titles import title_near_name
    assert title_near_name("Wen Sun was an assistant professor at Cornell. He is now a research scientist.", "Wen Sun") == ""
    assert title_near_name("Jane Doe, formerly Assistant Professor of CS at X", "Jane Doe") == ""
    assert title_near_name("Jane Doe is an Assistant Professor of CS at X", "Jane Doe").lower().startswith("assistant professor")


def test_titles_set_rejects_past_title(tmp_path, monkeypatch):
    import pytest
    from coverage import titles
    monkeypatch.setattr(titles, "DATA", tmp_path)
    (tmp_path / "coverage").mkdir()
    with pytest.raises(SystemExit):
        titles.main(["--school", "Cornell University", "--set", "A B", "--title", "former assistant professor", "--url", "u"])
    assert not (tmp_path / "coverage" / "titles.jsonl").exists()


def test_bowers_absolute_profile_href_not_joined():
    from coverage.bowers_dir import parse
    html = ('<div class="directory-card"><div class="name">Abc Def</div><div class="view-full-profile">'
            '<a href="https://www.google.com/search?q=x">p</a></div></div>')
    assert parse(html, "u", "CS")[0]["profile_url"] == "https://www.google.com/search?q=x"
    bad = html.replace("https://www.google.com/search?q=x", "https://www.duffield.cornell.edu/people/https://www.google.com/search?q=x-abc")
    assert parse(bad, "u", "CS")[0]["profile_url"] is None
