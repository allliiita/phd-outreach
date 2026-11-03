import copy
import json

from outreach import emailcheck as ec

A, P, O = ec.FIX_APP, ec.FIX_PACK, [ec.FIX_OTHER]


def errs(**mut):
    d = copy.deepcopy(ec.FIX_GOOD)
    for k, v in mut.items():
        d[k] = v(d[k]) if callable(v) else v
    return ec.check(d, P, A, O)


def has(es, frag):
    return any(frag in e for e in es)


def test_self_test_passes():
    assert ec.self_test() == 0


def test_good_draft_clean():
    assert errs() == []


def test_subject_format():
    assert has(errs(subject="Prospective PhD student - Lindsey Ma - X"), "subject must be")


def test_paragraph_count():
    assert has(errs(body=lambda b: b.replace("\n\nThank you for your time", " Thank you for your time")), "8 blocks")


def test_salutation_surname():
    assert has(errs(body=lambda b: b.replace("Dear Professor Quill,", "Dear Professor Quil,")), "salutation must be")


def test_p2_needs_pack_title_and_invented_title_rejected():
    es = errs(body=lambda b: b.replace("Calibrated Conformal Inference for Protein Language Models", "Conformal Magic for Everything Models"))
    assert has(es, "P2 does not contain") and has(es, "quoted text is not a pack paper title")


def test_word_count():
    cut = lambda b: b.replace(b.split("\n\n")[3], "Short P4 about my EEG decoder. Would you be considering PhD students for 2027 entry?").replace(b.split("\n\n")[2], "My broad research interest lies in calibration.")
    assert has(errs(body=cut), "words in paragraphs")
    assert has(errs(body=lambda b: b.replace("Thank you for your time", "word " * 80 + "Thank you for your time")), "words in paragraphs")


def test_banned_phrase():
    assert has(errs(body=lambda b: b.replace("I recently read", "I recently read your groundbreaking work, namely")), "banned phrase")


def test_invented_number():
    assert has(errs(body=lambda b: b.replace("77.4%", "87.4%")), "neither the pack nor applicant")


def test_p2_p4_same_project_rejected():
    c = lambda cl: [dict(x, source="applicant.projects.calcium") if x["para"] == 4 else x for x in cl]
    assert has(errs(claims=c), "same applicant project")


def test_claim_source_must_exist():
    assert has(errs(claims=lambda cl: cl + [{"para": 3, "text": "x", "source": "papers[5].title"}]), "claim source does not exist")
    assert has(errs(claims=lambda cl: cl + [{"para": 3, "text": "x", "source": "applicant.publications"}]), "claim source does not exist")


def test_other_professor_and_wrong_recipient():
    assert has(errs(body=lambda b: b.replace("your ongoing work", "the work of Professor Smith")), "another professor")
    assert has(errs(to="someone@else.edu"), "differs from pack email")


def test_swap_test_uses_other_packs():
    # words used by another pack are not "unique to this professor"
    other = dict(ec.FIX_OTHER, keywords=["calibration", "conformal"], research={"text": "calibration conformal foundation"})
    u = ec.unique_tokens(P, [other], A)
    assert "calibration" not in u and "conformal" not in u


def test_run_writes_check_file(tmp_path, monkeypatch):
    for sub in ("drafts", "packs"):
        (tmp_path / sub).mkdir()
    (tmp_path / "drafts" / "ada-quill-tu.json").write_text(json.dumps(ec.FIX_GOOD))
    (tmp_path / "packs" / "ada-quill-tu.json").write_text(json.dumps(P))
    monkeypatch.setattr(ec, "profile", lambda: A)
    assert ec.run(["ada-quill-tu"], tmp_path) == 0
    assert json.loads((tmp_path / "checks" / "ada-quill-tu.json").read_text())["ok"] is True
