"""check: waiting-on-human column; gridrow done guard; open:title outcome."""
import json

from coverage import check, gridrow, ledger, scope
from tests.test_coverage import SCHOOL, fixture


def test_waiting_on_human_has_own_column_but_stays_non_terminal(tmp_path, monkeypatch, capsys):
    fixture(tmp_path, monkeypatch, "blocked")
    (tmp_path / "coverage" / "human_requests.jsonl").write_text(
        json.dumps({"school": SCHOOL, "unit": "Computer Science", "url": "u", "why": "TLS"}) + "\n")
    assert check.main([]) == 1                      # still not done
    lines = capsys.readouterr().out.splitlines()
    assert "waiting on human" in lines[0]
    row = next(l for l in lines if l.startswith(SCHOOL))
    assert row.split()[-5:] == ["0", "0", "0", "0", "1"]   # units, recall, funnel, unverified = 0; waiting = 1


def test_title_less_in_scope_person_is_open_title_not_fit_pending(tmp_path, monkeypatch):
    (tmp_path / "roster").mkdir()
    (tmp_path / "roster" / "duke-cs.jsonl").write_text(json.dumps(
        {"name": "Wen Li", "institution": SCHOOL, "title_on_roster": "", "department": "CS", "profile_url": "u"}) + "\n")
    monkeypatch.setattr(ledger, "DATA", tmp_path)
    monkeypatch.setattr(scope, "schools", lambda: [SCHOOL])
    monkeypatch.setattr(scope, "faculty_like", lambda r: True)
    monkeypatch.setattr(ledger, "results", lambda: {})
    rows = ledger.build()
    assert rows[0]["in_scope"] and rows[0]["outcome"] == "open:title"


def test_gridrow_refuses_done_when_rows_differ_from_page_count(tmp_path, monkeypatch, capsys):
    (tmp_path / "grid").mkdir()
    monkeypatch.setattr(gridrow, "DATA", tmp_path)
    monkeypatch.setattr(gridrow, "SLUG", {SCHOOL: "duke"})
    r = tmp_path / "r.jsonl"
    r.write_text('{"name":"a"}\n{"name":"b"}\n')
    args = ["--school", SCHOOL, "--unit", "CS", "--status", "done", "--roster", str(r)]
    assert gridrow.main(args + ["--page-count", "3"]) == 2
    assert "diff -1" in capsys.readouterr().err and not (tmp_path / "grid" / "duke.jsonl").exists()
    assert gridrow.main(args + ["--page-count", "2"]) == 0
