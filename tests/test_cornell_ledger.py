"""Ledger title rules found by the Cornell pilot (2026-11-02)."""
import json

from coverage import scope


def _fixture(tmp_path, monkeypatch, rows_by_file, titles=None):
    from coverage import ledger
    for name, rows in rows_by_file.items():
        (tmp_path / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "coverage").mkdir(exist_ok=True)
    if titles:
        (tmp_path / "coverage" / "titles.jsonl").write_text("".join(json.dumps(t) + "\n" for t in titles))
    monkeypatch.setattr(ledger, "DATA", tmp_path)
    monkeypatch.setattr(ledger, "roster_files", lambda: [tmp_path / n for n in rows_by_file])
    monkeypatch.setattr(ledger, "results", lambda: {})
    monkeypatch.setattr(scope, "schools", lambda: ["Cornell University"])
    return ledger


def _r(title, dept):
    return {"name": "Wen Li", "institution": "Cornell University", "department": dept, "title_on_roster": title,
            "quote": f"Wen Li {title}", "roster_url": "u", "profile_url": "p"}


def test_senior_title_in_one_roster_beats_untitled_row_in_another(tmp_path, monkeypatch):
    # a CAM card without title made senior ORIE professors look "in scope, title unknown"
    ledger = _fixture(tmp_path, monkeypatch, {"a.jsonl": [_r("", "CAM")], "b.jsonl": [_r("Professor", "ORIE")]})
    (row,) = ledger.build()
    assert row["in_scope"] is False and row["title"] == "Professor"
    ledger = _fixture(tmp_path, monkeypatch, {"a.jsonl": [_r("", "CAM")], "b.jsonl": [_r("Assistant Professor", "ORIE")]})
    (row,) = ledger.build()
    assert row["in_scope"] is True and row["title"] == "Assistant Professor"


def test_fetched_title_override_decides_the_young_gate(tmp_path, monkeypatch):
    t = [{"school": "Cornell University", "name": "Wen Li", "title": "Professor", "source_url": "u"}]
    ledger = _fixture(tmp_path, monkeypatch, {"a.jsonl": [_r("", "CAM")]}, titles=t)
    (row,) = ledger.build()
    assert row["in_scope"] is False
