import json
import sys

import pytest

from outreach import send

APP = {"name": "Lindsey Ma", "sender_email": "me@test.edu", "cv_pdf": "cv.pdf", "portfolio_pdf": "port.pdf"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    email = tmp_path / "data" / "email"
    for s in ("drafts", "packs", "checks", "reviews"):
        (email / s).mkdir(parents=True)
    (tmp_path / "cv.pdf").write_bytes(b"%PDF-cv")
    (tmp_path / "port.pdf").write_bytes(b"%PDF-port")
    monkeypatch.setattr(send, "ROOT", tmp_path)
    monkeypatch.setattr(send, "EMAIL", email)
    monkeypatch.setattr(send, "BATCHES", email / "batches")
    monkeypatch.setattr(send, "SENT", tmp_path / "data" / "sent.jsonl")
    monkeypatch.setattr(send, "profile", lambda: APP)
    return email


def add(email, pid, ok=True, verdict="PASS", unit="CS", to=None):
    to = to or f"{pid}@test.edu"
    (email / "drafts" / f"{pid}.json").write_text(json.dumps({"id": pid, "to": to, "subject": "PhD Inquiry – Lindsey Ma – X", "body": "Dear Professor Y,\n\nbody"}))
    (email / "packs" / f"{pid}.json").write_text(json.dumps({"id": pid, "email": to, "school": "T", "units": [unit]}))
    (email / "checks" / f"{pid}.json").write_text(json.dumps({"ok": ok}))
    (email / "reviews" / f"{pid}.json").write_text(json.dumps({"verdict": verdict}))


def test_only_checked_and_passed_drafts_are_ready(env):
    add(env, "a")
    add(env, "b", ok=False)
    add(env, "c", verdict="REVISE")
    (env / "drafts" / "d.json").write_text(json.dumps({"id": "d", "skip": "thin"}))
    assert [d["id"] for d in send.ready_drafts(env)] == ["a"]


def test_batch_caps_two_per_department(env):
    for i in range(4):
        add(env, f"p{i}", unit="CS")
    add(env, "q", unit="Stats")
    send.make_batch(10)
    b = json.loads((env / "batches" / "001.json").read_text())
    assert len(b["drafts"]) == 3 and b["approved"] is False


def test_mime_has_subject_and_both_attachments(env):
    import base64
    from email import message_from_bytes
    raw = send._mime({"to": "a@test.edu", "subject": "PhD Inquiry – Lindsey Ma – X", "body": "hi"})["raw"]
    m = message_from_bytes(base64.urlsafe_b64decode(raw))
    assert [p.get_filename() for p in m.walk() if p.get_filename()] == ["cv.pdf", "port.pdf"]


def test_approve_refuses_without_tty(env, monkeypatch):
    add(env, "a")
    send.make_batch(5)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit) as e:
        send.approve(1)
    assert "interactive terminal" in str(e.value)
    assert json.loads((env / "batches" / "001.json").read_text())["approved"] is False


def test_send_requires_approval(env):
    add(env, "a")
    send.make_batch(5)
    with pytest.raises(SystemExit):
        send.send(1)


class FakeGmail:
    def __init__(self):
        self.created, self.sent = [], []

    def users(self):
        return self

    def drafts(self):
        outer = self

        class D:
            def create(self, userId, body):
                outer.created.append(body)
                return type("E", (), {"execute": lambda s: {"id": f"g{len(outer.created)}"}})()
        return D()

    def messages(self):
        outer = self

        class M:
            def send(self, **kw):
                outer.sent.append(kw)
                raise AssertionError("drafts must never send")
        return M()


def test_drafts_created_not_sent_idempotent_and_stale_skipped(env, monkeypatch):
    add(env, "a")
    add(env, "b")
    send.make_batch(5)
    g = FakeGmail()
    monkeypatch.setattr(send, "_gmail", lambda: g)
    # b is edited after the batch was made -> must not be drafted
    f = env / "drafts" / "b.json"
    d = json.loads(f.read_text())
    d["body"] += " edited"
    f.write_text(json.dumps(d))
    send.to_drafts(1)
    assert len(g.created) == 1 and g.sent == []
    send.to_drafts(1)
    assert len(g.created) == 1
    assert [json.loads(l)["id"] for l in (env / "gmail_drafts.jsonl").read_text().splitlines()] == ["a"]
