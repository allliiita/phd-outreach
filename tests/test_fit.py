"""coverage.fit: stable card ids, two-judge merge with tiebreak, ledger mapping of decided fits."""
import json

from coverage import fit, ledger, scope

S = "Cornell University"
NAMES = ["Wen Li", "Ann Wu", "Bo Xu", "Cy Ma"]


def _w(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _setup(tmp_path, monkeypatch, names):
    monkeypatch.setattr(fit, "DATA", tmp_path)
    monkeypatch.setattr(fit, "FIT", tmp_path / "fit")
    monkeypatch.setattr(scope, "school_of", lambda i: S)
    people = [{"school": S, "name": n, "key": list(scope.name_key(n)), "in_scope": True, "outcome": "open",
               "title": "Assistant Professor", "units": ["CS"], "profile_url": None,
               "gates": {"faculty": True, "young": True, "heritage": True}} for n in names]
    _w(tmp_path / "coverage" / "people.jsonl", people)


def test_card_id_stable_and_credential_proof():
    assert fit.card_id(S, "Wen Li") == fit.card_id(S, "Wen Li") and fit.card_id(S, "Wen Li").startswith("cornell:")
    assert fit.card_id(S, "Wu Chen PhD") == fit.card_id(S, "Wu Chen")


def test_cards_skip_decided_and_are_stable(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, ["Wen Li", "Ann Wu"])
    _w(tmp_path / "fit" / "decided.jsonl", [{"id": fit.card_id(S, "Ann Wu"), "fit": "A"}])
    a = fit.build_cards(S, fetch=False)
    assert [c["id"] for c in a] == [fit.card_id(S, "Wen Li")]
    assert a == fit.build_cards(S, fetch=False)


def _judge(tmp_path, judge, fits):
    _w(tmp_path / "fit" / "out" / f"cornell.{judge}.jsonl",
       [{"id": fit.card_id(S, n), "fit": f, "theme": "other", "summary": "s", "hook": ""} for n, f in fits.items()])


def test_merge_agree_disagree_tiebreak(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, NAMES[:3])
    fit.cmd_cards(S, fetch=False)
    _judge(tmp_path, "opus", {"Wen Li": "A", "Ann Wu": "A", "Bo Xu": "?"})
    _judge(tmp_path, "haiku", {"Wen Li": "A", "Ann Wu": "C", "Bo Xu": "B"})
    r = fit.merge(S)
    assert r["decided"] == 1 and r["tiebreak"] == 2
    tie = [json.loads(x)["id"] for x in (tmp_path / "fit" / "tiebreak" / "cornell.jsonl").read_text().splitlines()]
    assert set(tie) == {fit.card_id(S, "Ann Wu"), fit.card_id(S, "Bo Xu")}
    _judge(tmp_path, "tiebreak", {"Ann Wu": "C", "Bo Xu": "?"})
    fit.merge(S)
    d = fit.decided()
    assert d[fit.card_id(S, "Wen Li")]["judges"] == ["haiku", "opus"]
    assert d[fit.card_id(S, "Ann Wu")]["fit"] == "C" and d[fit.card_id(S, "Bo Xu")]["fit"] == "?"
    assert not (tmp_path / "fit" / "tiebreak" / "cornell.jsonl").read_text().strip()


def test_ledger_maps_decided(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "DATA", tmp_path)
    monkeypatch.setattr(scope, "school_of", lambda i: S)
    _w(tmp_path / "fit" / "decided.jsonl",
       [{"id": fit.card_id(S, n), "school": S, "name": n, "fit": f} for n, f in zip(NAMES, "CAB?")])
    res = ledger.results()
    out = {n: ledger.outcome(res[(S, scope.name_key(n))]) for n in NAMES}
    assert out["Wen Li"] == "rejected:not ML"
    assert out["Ann Wu"] == out["Bo Xu"] == "open:verify"
    assert out["Cy Ma"].startswith("open:fit")


def test_batch_merge_agree_and_disagree(tmp_path, monkeypatch):
    monkeypatch.setattr(fit, "FIT", tmp_path / "fit")
    cards = [{"id": f"cornell:p{i}", "name": f"P{i}", "school": S, "research": "x", "home": "", "papers": []} for i in range(3)]
    _w(tmp_path / "fit" / "in" / "cornell.jsonl", cards)
    assert fit.make_batches(2) == [2, 1]
    j = lambda i, f: {"id": f"cornell:p{i}", "fit": f, "theme": "t", "summary": "s", "hook": "h"}
    _w(tmp_path / "fit" / "out" / "batch-b01.opus.jsonl", [j(0, "A"), j(1, "A"), j(2, "B")])
    _w(tmp_path / "fit" / "out" / "batch-b01.haiku.jsonl", [j(0, "A"), j(1, "C")])
    r = fit.merge_batches()
    d = fit.decided()
    assert r == {"decided": 2, "waiting": 1}
    assert d["cornell:p0"]["fit"] == "A" and "note" not in d["cornell:p0"]
    assert d["cornell:p1"]["fit"] == "?" and d["cornell:p1"]["note"] == "judges disagree: C vs A"
    assert "cornell:p2" not in d
