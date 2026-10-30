"""Sending. Sending is irreversible, so a human approves every batch, and the approval step
structurally requires an interactive terminal: an agent running commands cannot approve.

  python -m outreach.send batch --size 20      # pick next 20 checked+verified drafts -> data/batches/NNN.json
  python -m outreach.send show 3               # print batch 3 for review
  python -m outreach.send drafts 3             # put batch 3 into Gmail Drafts (safe; you press send in Gmail)
  python -m outreach.send approve 3            # HUMAN ONLY: needs a TTY and typing the batch number
  python -m outreach.send send 3               # send approved batch 3 via Gmail API, paced

Pacing: <= DAILY_CAP per day, <= 2 per department per day, 60-180 s apart.
Never sends to anyone already in data/sent.jsonl.
"""
from __future__ import annotations

import base64
import json
import random
import sys
import time
from collections import Counter
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

from .config import ROOT, profile

DATA = ROOT / "data"
BATCHES = DATA / "batches"
SENT = DATA / "sent.jsonl"
DAILY_CAP = 40
PER_DEPT_PER_DAY = 2
SCOPES = ["https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/gmail.send"]


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def _gmail():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    tok = ROOT / "secrets" / "token.json"
    creds = Credentials.from_authorized_user_file(tok, SCOPES) if tok.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:  # opens a browser window for the human to log in once
            creds = InstalledAppFlow.from_client_secrets_file(ROOT / "secrets" / "credentials.json", SCOPES).run_local_server(port=0)
        tok.parent.mkdir(exist_ok=True)
        tok.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _mime(d: dict) -> dict:
    app = profile()
    m = EmailMessage()
    m["To"], m["From"], m["Subject"] = d["to"], app["sender_email"], d["subject"]
    m.set_content(d["body"])
    cv = ROOT / app["cv_pdf"]
    m.add_attachment(cv.read_bytes(), maintype="application", subtype="pdf", filename="Lindsey_Ma_CV.pdf")
    return {"raw": base64.urlsafe_b64encode(m.as_bytes()).decode()}


def make_batch(size: int) -> None:
    ready = [d for d in _jsonl(DATA / "drafts.jsonl") if d.get("status") == "checked"]
    sent_to = {s["to"].lower() for s in _jsonl(SENT)}
    batched = {d["id"] for b in BATCHES.glob("*.json") for d in json.loads(b.read_text())["drafts"]}
    pick, per_dept = [], Counter()
    for d in ready:
        if d["to"].lower() in sent_to or d["id"] in batched:
            continue
        key = d.get("dept_key", d["id"].rsplit("-", 1)[-1])
        if per_dept[key] >= PER_DEPT_PER_DAY:
            continue
        per_dept[key] += 1
        pick.append(d)
        if len(pick) == size:
            break
    BATCHES.mkdir(parents=True, exist_ok=True)
    n = len(list(BATCHES.glob("*.json"))) + 1
    (BATCHES / f"{n:03d}.json").write_text(json.dumps({"n": n, "approved": False, "drafts": pick}, indent=1))
    print(f"batch {n}: {len(pick)} drafts -> review with: python -m outreach.send show {n}")


def show(n: int) -> None:
    b = json.loads((BATCHES / f"{n:03d}.json").read_text())
    for d in b["drafts"]:
        print(f"\n=== {d['id']}  ->  {d['to']}\nSubject: {d['subject']}\n\n{d['body']}")
    print(f"\n{len(b['drafts'])} emails. approved={b['approved']}")


def approve(n: int) -> None:
    if not sys.stdin.isatty():
        sys.exit("approve must be run by a human in an interactive terminal")
    show(n)
    if input(f"\nType the batch number ({n}) to approve sending these emails: ").strip() != str(n):
        sys.exit("not approved")
    p = BATCHES / f"{n:03d}.json"
    b = json.loads(p.read_text())
    b["approved"], b["approved_at"] = True, datetime.now().isoformat(timespec="seconds")
    p.write_text(json.dumps(b, indent=1))
    print("approved")


def to_drafts(n: int) -> None:
    g = _gmail()
    for d in json.loads((BATCHES / f"{n:03d}.json").read_text())["drafts"]:
        g.users().drafts().create(userId="me", body={"message": _mime(d)}).execute()
        print("drafted", d["id"])


def send(n: int) -> None:
    b = json.loads((BATCHES / f"{n:03d}.json").read_text())
    if not b.get("approved"):
        sys.exit(f"batch {n} is not approved by a human")
    today = str(date.today())
    sent = _jsonl(SENT)
    sent_to = {s["to"].lower() for s in sent}
    count_today = sum(s["date"] == today for s in sent)
    g = _gmail()
    for d in b["drafts"]:
        if d["to"].lower() in sent_to:
            continue
        if count_today >= DAILY_CAP:
            print(f"daily cap {DAILY_CAP} reached; resume tomorrow")
            return
        r = g.users().messages().send(userId="me", body=_mime(d)).execute()
        with SENT.open("a") as f:
            f.write(json.dumps({"id": d["id"], "to": d["to"], "date": today, "gmail_id": r["id"], "batch": n}) + "\n")
        count_today += 1
        print("sent", d["id"])
        time.sleep(random.uniform(60, 180))


def main() -> None:
    cmd, *rest = sys.argv[1:]
    if cmd == "batch":
        make_batch(int(rest[rest.index("--size") + 1]) if "--size" in rest else 20)
    else:
        {"show": show, "approve": approve, "drafts": to_drafts, "send": send}[cmd](int(rest[0]))


if __name__ == "__main__":
    main()
