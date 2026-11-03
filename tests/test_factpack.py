from datetime import date

from outreach import factpack as fp

APP = {"projects": [
    {"key": "calcium", "one_liner": "Calcium imaging denoising.", "matches": ["neuroscience", "denoising"]},
    {"key": "flywire", "one_liner": "SBM on FlyWire.", "matches": ["graph", "Bayesian"]},
    {"key": "eeg", "one_liner": "EEG decoder.", "matches": ["EEG"]}]}
TODAY = date(2026, 11, 3)
ROW = {"school": "Test University", "name": "Wei Wu PhD", "title": "Assistant Professor", "email": "ww@test.edu",
       "homepage": "https://wu.example/", "department(s)": "CS; Stats", "theme": "graph learning", "summary": "", "email source": "https://x"}
TITLE = "Spectral Graph Denoising at Scale"


def test_surname_keeps_name_with_credentials_and_particles():
    assert fp.surname("Wei Wu PhD") == "Wu"
    assert fp.surname("Jane Doe, Ph.D.") == "Doe"
    assert fp.surname("Marten van Schijndel") == "van Schijndel"
    assert fp.salutation("Xuezhou (Jack) Zhang") == "Professor Zhang"


def test_title_in_is_verbatim_modulo_case_and_punct():
    assert fp.title_in(TITLE, "x 2025. spectral graph denoising, at scale! y")
    assert fp.title_in(TITLE, "spectral graph denoising") is None


def test_match_projects_top2_and_weak_flag():
    m = fp.match_projects(["graph learning with Bayesian priors for neuroscience"], APP["projects"])
    assert {x["key"] for x in m} == {"calcium", "flywire"}
    assert all(not x["weak"] for x in m)
    assert fp.match_projects(["databases"], APP["projects"])[0]["weak"]


def _idx(papers):
    return {("test university", "wei wu phd"): {"id": "wei-wu-tu", "recent_papers": papers, "keywords": ["graph learning"]}}, {}


def test_pack_only_with_page_verified_paper():
    people, dos = _idx([{"title": TITLE, "year": 2025}])
    page = lambda u: f"<html><body>{'padding ' * 100} Publications: {TITLE}. NeurIPS 2025</body></html>"
    pack, why = fp.build_pack(ROW, people, dos, fetch_page=page, fetch_json=lambda u: {}, applicant=APP, today=TODAY)
    assert pack and pack["papers"][0]["title"] == TITLE and pack["papers"][0]["source_url"] == "https://wu.example/"
    assert pack["salutation"] == "Professor Wu" and pack["units"] == ["CS", "Stats"]


def test_openalex_only_paper_is_skipped():
    people, dos = _idx([{"title": TITLE, "year": 2025}])
    pack, why = fp.build_pack(ROW, people, dos, fetch_page=lambda u: "<html>nothing here</html>", fetch_json=lambda u: {}, applicant=APP, today=TODAY)
    assert pack is None and "no recent paper" in why


def test_old_paper_not_used():
    people, dos = _idx([{"title": TITLE, "year": 2019}])
    pack, _ = fp.build_pack(ROW, people, dos, fetch_page=lambda u: TITLE, fetch_json=lambda u: {}, applicant=APP, today=TODAY)
    assert pack is None


def _dblp(aff):
    def f(url):
        if "author/api" in url:
            return {"result": {"hits": {"hit": [{"info": {"author": "Wei Wu 0002", "url": "https://dblp.org/pid/1/2",
                    "notes": {"note": {"@type": "affiliation", "text": aff}}}}]}}}
        return {"result": {"hits": {"hit": [{"info": {"title": "A Dblp Paper Title Here.", "year": "2025", "venue": "ICML", "ee": "https://doi.org/x",
                "authors": {"author": [{"text": "Wei Wu 0002"}, {"text": "Ann Lee"}]}}}]}}}
    return f


def test_dblp_requires_affiliation_match():
    got = fp.dblp_papers("Wei Wu", "Test University", _dblp("Test University, Dept of CS"), 2023)
    assert got and got[0]["coauthors"] == ["Ann Lee"] and got[0]["title"] == "A Dblp Paper Title Here"
    assert fp.dblp_papers("Wei Wu", "Test University", _dblp("Other College"), 2023) == []
