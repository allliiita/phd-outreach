"""Deterministic checks of a drafted email against its fact pack (layer 2 of the email stage).

  python -m outreach.emailcheck ID [ID ...]     # data/email/drafts/<id>.json vs data/email/packs/<id>.json
  python -m outreach.emailcheck --all           # every draft
  python -m outreach.emailcheck --self-test     # fixture good draft passes, generic draft fails the swap test
Writes data/email/checks/<id>.json {ok, errors}; exit 1 if any draft fails.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .config import ROOT, profile

EMAIL = ROOT / "data" / "email"
BANNED = [
    "hope this email finds you", "deeply passionate", "groundbreaking", "esteemed", "renowned",
    "i have read all", "your impressive work", "your inspiring work", "delve", "recommendation letter",
    "letter of recommendation", "recommender", "my publication", "my paper", "i published", "tapestry",
    "i am writing to express my", "cutting-edge", "cutting edge", "state-of-the-art", "i am passionate", "world-class",
]
WORDS = (230, 330)
STOP = set("""about their which these those there where would could should being between through under other
research learning model models methods method using based approach approaches paper papers machine data systems system
university professor group work works study studies analysis new novel large language neural network networks deep""".split())


def norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", (s or "").lower())
    return " ".join(s.split())


def _tokens(s: str) -> set[str]:
    return {t for t in norm(s).split() if len(t) >= 5 and t not in STOP and not t.isdigit()}


def applicant_text(app: dict) -> str:
    return json.dumps(app, ensure_ascii=False)


def pack_text(pack: dict) -> str:
    parts = [pack.get("research", {}) and pack["research"].get("text", ""), " ".join(pack.get("keywords") or []),
             pack.get("theme") or "", " ".join(pack.get("units") or []), pack.get("title", "")]
    for p in pack.get("papers", []):
        parts += [p["title"], p.get("venue", ""), " ".join(p.get("coauthors", []))]
    if pack.get("recruiting"):
        parts.append(pack["recruiting"]["quote"])
    return " ".join(str(x) for x in parts if x)


def unique_tokens(pack: dict, others: list[dict], app: dict) -> set[str]:
    """Tokens of this professor's pack (paper titles, research text, keywords) that the applicant's own text lacks and
    that no other pack uses: words that, if absent from the draft, mean the draft could go to anyone."""
    mine = _tokens(" ".join([pack_text(pack)]))
    mine -= _tokens(applicant_text(app))
    for o in others:
        mine -= _tokens(pack_text(o))
    return mine


def resolve(path: str, pack: dict, app: dict):
    """Value at a claim source: 'papers[0].title', 'research.text', 'applicant.projects.calcium', 'applicant.degree'."""
    if path.startswith("applicant."):
        cur, parts = app, path.split(".")[1:]
        if parts[:1] == ["projects"] and len(parts) >= 2:
            cur = next((p for p in app.get("projects", []) if p["key"] == parts[1]), None)
            parts = parts[2:] or ["one_liner"]
    else:
        cur, parts = pack, path.split(".")
    for part in parts:
        if cur is None:
            return None
        m = re.fullmatch(r"(\w+)\[(\d+)\]", part)
        if m:
            cur = cur.get(m.group(1)) if isinstance(cur, dict) else None
            cur = cur[int(m.group(2))] if isinstance(cur, list) and int(m.group(2)) < len(cur) else None
        else:
            cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def split_blocks(body: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", body.strip()) if b.strip()]


def check(d: dict, pack: dict, app: dict, others: list[dict] | None = None) -> list[str]:
    errs: list[str] = []
    name = app["name"]
    subj, body = d.get("subject", ""), d.get("body", "")
    if d.get("id") != pack.get("id"):
        errs.append(f"draft id {d.get('id')!r} != pack id {pack.get('id')!r}")
    if d.get("to", "").lower() != pack["email"].lower():
        errs.append(f"to={d.get('to')!r} differs from pack email {pack['email']!r}")
    m = re.fullmatch(rf"PhD Inquiry – {re.escape(name)} – (.{{3,80}})", subj)
    if not m:
        errs.append(f"subject must be 'PhD Inquiry – {name} – <Topic>' (en dashes): {subj!r}")

    blocks = split_blocks(body)
    if len(blocks) != 8:
        errs.append(f"want salutation + 6 paragraphs + sign-off = 8 blocks, got {len(blocks)}")
        paras = blocks[1:-1]
    else:
        paras = blocks[1:7]
        if blocks[-1] != f"Sincerely,\n{name}":
            errs.append(f"sign-off must be 'Sincerely,\\n{name}': {blocks[-1]!r}")
    if blocks:
        sal = f"Dear {pack['salutation']},"
        if blocks[0] != sal:
            errs.append(f"salutation must be {sal!r}: {blocks[0]!r}")
    text = "\n\n".join(paras)
    n = len(text.split())
    if not WORDS[0] <= n <= WORDS[1]:
        errs.append(f"{n} words in paragraphs (want {WORDS[0]}-{WORDS[1]})")

    if len(paras) == 6:
        p = paras
        if name not in p[0] or "prospective PhD applicant" not in p[0]:
            errs.append("P1 must say 'I am <name>, a prospective PhD applicant ...'")
        titles = [x["title"] for x in pack.get("papers", [])]
        hit = [t for t in titles if norm(t) in norm(p[1])]
        if not hit:
            errs.append("P2 does not contain a pack paper title verbatim")
        elif not re.search(r"[\"“”']" , p[1]):
            errs.append("P2 must put the paper title in quotation marks")
        if "broad research interest" not in p[2].lower():
            errs.append("P3 must state 'My broad research interest lies in ...'")
        if "2027" not in p[3] or "?" not in p[3]:
            errs.append("P4 must end with the question about PhD students for 2027 entry")
        if "cv" not in p[4].lower() or "attached" not in p[4].lower():
            errs.append("P5 must say the CV and portfolio are attached")
        if "thank you" not in p[5].lower():
            errs.append("P6 must be the thank-you / brief discussion paragraph")
    for q in re.findall(r"[\"“]([^\"”]{12,})[\"”]", body):
        if not any(norm(q) == norm(t) or norm(q) in norm(t) for t in [x["title"] for x in pack.get("papers", [])]):
            errs.append(f"quoted text is not a pack paper title: {q[:60]!r}")

    low = (subj + "\n" + body).lower()
    for b in BANNED:
        if b in low:
            errs.append(f"banned phrase: {b!r}")
    if not app.get("mention_recommenders", False) and "recommend" in low:
        errs.append("mentions recommendation")
    for other in re.findall(r"Professor\s+([A-Z][\w'’-]+)", body):
        if other.lower() not in pack["surname"].lower():
            errs.append(f"mentions another professor: {other}")

    # numbers must come from the pack or applicant.yaml
    allowed = set(re.findall(r"\d+(?:\.\d+)?", pack_text(pack) + " " + applicant_text(app) + " " + json.dumps(pack.get("papers", []))))
    for num in set(re.findall(r"\d+(?:\.\d+)?", body)):
        if num not in allowed and num != "2027":
            errs.append(f"number {num!r} is in neither the pack nor applicant.yaml")

    # claims
    claims = d.get("claims")
    if not isinstance(claims, list) or not claims:
        errs.append("claims missing")
        claims = []
    projs = {2: set(), 4: set()}
    for c in claims:
        src = c.get("source", "")
        if not c.get("text") or not src:
            errs.append(f"claim needs text and source: {c}")
        elif resolve(src, pack, app) in (None, "", []):
            errs.append(f"claim source does not exist: {src!r}")
        mm = re.fullmatch(r"applicant\.projects\.(\w+)(?:\.one_liner)?", src)
        if mm and c.get("para") in projs:
            projs[c["para"]].add(mm.group(1))
        if not src.startswith("applicant.") and src.split(".")[0].split("[")[0] not in pack:
            errs.append(f"claim source is neither pack nor applicant: {src!r}")
    if not any(c.get("source", "").startswith("papers[") for c in claims if c.get("para") == 2):
        errs.append("P2 needs a claim sourced from papers[i]")
    if not projs[2] or not projs[4]:
        errs.append("P2 and P4 each need a claim sourced from applicant.projects.<key> (claim.para = 2 / 4)")
    elif projs[2] & projs[4] and len(app.get("projects", [])) > 1:
        errs.append(f"P2 and P4 use the same applicant project: {sorted(projs[2] & projs[4])}")

    # swap test
    uniq = unique_tokens(pack, others or [], app)
    stripped = norm(body)
    for t in (x["title"] for x in pack.get("papers", [])):
        stripped = stripped.replace(norm(t), " ")   # quoting the title is required, so it cannot prove specificity
    found = sorted(t for t in uniq if t in set(stripped.split()))
    if len(found) < 2:
        errs.append(f"swap test failed: only {len(found)} tokens unique to this professor outside the quoted title (need 2); e.g. {sorted(uniq)[:6]}")
    return errs


def load_others(pid: str, packs_dir: Path | None = None) -> list[dict]:
    d = packs_dir or EMAIL / "packs"
    return [json.loads(p.read_text()) for p in d.glob("*.json") if p.stem != pid]


def run(ids: list[str], email: Path = EMAIL) -> int:
    app, bad = profile(), 0
    (email / "checks").mkdir(parents=True, exist_ok=True)
    for i in ids:
        try:
            d = json.loads((email / "drafts" / f"{i}.json").read_text())
            if "skip" in d:
                raise ValueError(f"writer skipped this professor: {d['skip']}")
            pack = json.loads((email / "packs" / f"{i}.json").read_text())
            errs = check(d, pack, app, load_others(i, email / "packs"))
        except (OSError, ValueError, KeyError) as e:
            errs = [f"cannot check: {type(e).__name__}: {e}"]
        (email / "checks" / f"{i}.json").write_text(json.dumps({"id": i, "ok": not errs, "errors": errs}, indent=1))
        for e in errs:
            print(f"{i}\t{e}")
        bad += bool(errs)
    print(f"# {len(ids)} drafts, {bad} failing", file=sys.stderr)
    return 1 if bad else 0


# ---------- self-test fixtures ----------

FIX_APP = {"name": "Lindsey Ma", "mention_recommenders": False, "degree": "M.S. in Statistics, Columbia University (2026)",
           "projects": [
               {"key": "calcium", "one_liner": "I worked on self-supervised denoising of two-photon calcium imaging.", "matches": []},
               {"key": "eeg", "one_liner": "I built a real-time EEG motor-imagery decoder, raising accuracy from 67.9% to 77.4%.", "matches": []}]}
FIX_PACK = {"id": "ada-quill-tu", "name": "Ada Quill", "salutation": "Professor Quill", "surname": "Quill", "title": "Assistant Professor",
            "school": "Test University", "units": ["Computer Science"], "email": "aquill@test.edu",
            "research": {"text": "My group studies conformal prediction and calibration for scientific foundation models.", "source_url": "https://q.example"},
            "keywords": ["conformal prediction", "calibration"], "theme": "uncertainty",
            "papers": [{"title": "Calibrated Conformal Inference for Protein Language Models", "year": 2025, "coauthors": ["B. Roe"],
                        "venue": "ICML", "source_url": "https://q.example/pubs", "verified_in": "page"}],
            "recruiting": None}
FIX_OTHER = {"id": "x", "name": "X Y", "research": {"text": "robotics manipulation grasping"}, "keywords": ["robotics"], "papers": [], "units": []}
GOOD_BODY = """Dear Professor Quill,

I am Lindsey Ma, a prospective PhD applicant interested in uncertainty quantification, conformal prediction and trustworthy scientific machine learning. I hold an M.S. in Statistics from Columbia University and have since focused on self-supervised methods for biological imaging data.

I recently read your 2025 paper "Calibrated Conformal Inference for Protein Language Models" (with B. Roe, ICML). I was particularly interested in how calibration guarantees are kept valid when the underlying protein language model is a fixed foundation model. This resonated with my experience on self-supervised denoising of two-photon calcium imaging, where I had to judge denoised signals against synthetic benchmarks without trusting the model blindly.

My broad research interest lies in statistical machine learning for scientific data. More specifically, I am interested in calibration and conformal methods that remain honest when foundation models are applied to biological measurements. I see this as a direction I would like to develop further under supervision.

In a separate project I built a real-time EEG motor-imagery decoder, raising accuracy from 67.9% to 77.4% over a CSP-LDA baseline, using run-grouped validation so that the gain was not an artefact of leakage between recording sessions. That experience made me care about calibrated claims. I would be interested in learning how your research group approaches calibration for foundation models in practice. Would you be considering PhD students for 2027 entry?

My CV and selected project portfolio are attached for your reference. I would be happy to share my academic transcript and a research concept note upon request.

Thank you for your time and consideration. I would appreciate the opportunity for a brief discussion if my research interests might be relevant to your ongoing work.

Sincerely,
Lindsey Ma"""
FIX_GOOD = {"id": "ada-quill-tu", "to": "aquill@test.edu", "subject": "PhD Inquiry – Lindsey Ma – Conformal Prediction for Foundation Models",
            "body": GOOD_BODY,
            "claims": [{"para": 2, "text": "paper title", "source": "papers[0].title"},
                       {"para": 2, "text": "denoising project", "source": "applicant.projects.calcium"},
                       {"para": 4, "text": "EEG decoder", "source": "applicant.projects.eeg"},
                       {"para": 1, "text": "degree", "source": "applicant.degree"}]}


def self_test() -> int:
    ok = True
    errs = check(FIX_GOOD, FIX_PACK, FIX_APP, [FIX_OTHER])
    print("good draft:", "PASS" if not errs else f"FAIL {errs}")
    ok &= not errs
    generic = json.loads(json.dumps(FIX_GOOD))
    generic["body"] = re.sub(r'Calibrated Conformal Inference for Protein Language Models', "Calibrated Conformal Inference for Protein Language Models", GOOD_BODY)
    for a, b in [("conformal prediction and trustworthy", "machine learning and trustworthy"),
                 ("how calibration guarantees are kept valid when the underlying protein language model is a fixed foundation model",
                  "the strong empirical results and the clear writing"),
                 ("calibration and conformal methods that remain honest when foundation models", "modern methods that remain honest when models"),
                 ("calibration for foundation models", "your methods"), ("calibrated claims", "careful claims"),
                 ("uncertainty quantification, ", "")]:
        generic["body"] = generic["body"].replace(a, b)
    generic["body"] = generic["body"].replace('"Calibrated Conformal Inference for Protein Language Models" (with B. Roe, ICML)', '"Calibrated Conformal Inference for Protein Language Models"')
    gerrs = check(generic, FIX_PACK, FIX_APP, [FIX_OTHER])
    swap = [e for e in gerrs if e.startswith("swap test failed")]
    print("generic draft:", "FAIL (swap test) as expected" if swap else f"UNEXPECTED {gerrs}")
    ok &= bool(swap)
    # a draft with no paper title in P2 must also fail
    nopaper = json.loads(json.dumps(FIX_GOOD))
    nopaper["body"] = GOOD_BODY.replace("Calibrated Conformal Inference for Protein Language Models", "a recent paper")
    ok &= any("P2 does not contain" in e for e in check(nopaper, FIX_PACK, FIX_APP, [FIX_OTHER]))
    print("self-test", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main() -> None:
    a = sys.argv[1:]
    if a == ["--self-test"]:
        sys.exit(self_test())
    ids = sorted(p.stem for p in (EMAIL / "drafts").glob("*.json")) if a == ["--all"] else a
    if not ids:
        sys.exit(__doc__)
    sys.exit(run(ids))


if __name__ == "__main__":
    main()
