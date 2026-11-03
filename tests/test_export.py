"""coverage.export on a fixture: listed + fit-judged + disagree rows, priority sort, email rules, xlsx written."""
from coverage import export

S = "Cornell University"


def _row(name, outcome, fit=None, sources=("a.jsonl",)):
    return {"school": S, "name": name, "key": name.lower().split(), "in_scope": True, "title": "Assistant Professor",
            "units": ["Computer Science"], "sources": list(sources), "profile_url": "https://x.edu/p", "outcome": outcome, "fit": fit}


def test_rows_sorted_and_labelled(tmp_path):
    ledger = [_row("Ann Wu", "listed", "B"), _row("Bo Xu", "open:verify", "A"), _row("Cy Ma", "open:fit", "?"),
              _row("Di Li", "open"), _row("Ed Hu", "rejected:not ML", "C")]

    def k(n):
        return S, export.scope.name_key(n)
    src = {"tags": {k("Ann Wu"): {"theme": "core-ML/CV", "summary": "s", "hook": "h"}},
           "verify": {k("Ann Wu"): {"email": "ann@cornell.edu", "official_page": "https://x.edu/o", "title": "Asst Prof"}},
           "dblp": {}, "dossier": {},
           "decided": {k("Bo Xu"): {"fit": "A", "theme": "NeuroAI", "summary": "bs", "hook": "bh", "judges": ["o", "h"]},
                       k("Cy Ma"): {"fit": "?", "theme": "x", "summary": "cs", "note": "judges disagree: A vs C"}},
           "groups": {"a.jsonl": "G1"}}
    rows = export.build_rows(ledger, src, fetch=False)
    assert [r["name"] for r in rows] == ["Bo Xu", "Ann Wu", "Cy Ma"]   # NeuroAI first; Di Li (unjudged), Ed Hu (C) absent
    by = {r["name"]: r for r in rows}
    assert by["Ann Wu"]["evidence status"] == "verified-earlier" and by["Ann Wu"]["email"] == "ann@cornell.edu"
    assert by["Bo Xu"]["evidence status"] == "fit-judged-not-record-verified" and by["Bo Xu"]["email"] == ""
    assert by["Cy Ma"]["evidence status"] == "judges-disagree" and "disagree" in by["Cy Ma"]["summary"]
    out = tmp_path / "x.xlsx"
    export.write_xlsx(rows, [{"kind": "open:title", "school": S, "item": "Z", "detail": "d"}], out)
    from openpyxl import load_workbook
    wb = load_workbook(out)
    assert wb.sheetnames == ["Advisors", "Not done"] and wb["Advisors"].max_row == 4 and wb["Not done"].max_row == 2


def test_priority_tiers():
    assert export.priority("NeuroAI", set()) == 1 and export.priority("x", {"G2"}) == 2
    assert export.priority("x", {"G1"}) == 3 and export.priority("x", {"G3"}) == 4
    assert export.priority("x", {"G3"}, ml_top=3) == 3
