import json

from coverage import check, scope

P1 = "https://www.bu.edu/cds-faculty/directory/?num=1"
P2 = "https://www.bu.edu/cds-faculty/directory/?num=2"


def test_unverified_searches_all_pages_of_paginated_roster(tmp_path, monkeypatch):
    for d in ("roster", "tag", "verify"):
        (tmp_path / d).mkdir()
    rows = [{"name": "A B", "roster_url": P1}, {"name": "Boqing Gong", "roster_url": P2}]
    (tmp_path / "roster" / "bu.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "tag" / "people.jsonl").write_text(json.dumps({"id": "x1", "name": "Boqing Gong", "institution": "Boston University"}) + "\n")
    (tmp_path / "verify" / "result.jsonl").write_text(json.dumps(
        {"id": "x1", "name": "Boqing Gong", "institution": "Boston University", "email": "bgong@bu.edu",
         "official_page": P2, "ml_quote": "research on machine learning"}) + "\n")
    monkeypatch.setattr(check, "DATA", tmp_path)
    snaps = {P1: ("raw1", "Boqing Gong research on machine learning bgong@bu.edu"), P2: ("raw2", "Boqing Gong")}
    import outreach.verify as v
    import outreach.fetch as f
    monkeypatch.setattr(v, "page", lambda u: snaps.get(u))
    monkeypatch.setattr(v, "quote_ok", lambda u, q: "" if q in snaps[u][1] else "quote not on page")
    monkeypatch.setattr(f, "emails", lambda raw: [("bgong@bu.edu", "")] if raw == "raw1" else [])
    led = [{"in_scope": True, "outcome": "listed", "school": scope.school_of("Boston University"), "key": list(scope.name_key("Boqing Gong")),
            "name": "Boqing Gong"}]
    assert check.unverified(led) == []
    assert check.roster_pages(P2) == [P2, P1]
