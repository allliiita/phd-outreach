"""Cards carry the person's own homepage text and paper titles (2026-11-03: profile paragraph alone was too thin)."""
import json

from coverage import fit, scope

S = "Cornell University"
PROFILE = '<html><body><p>Wen Li, Assistant Professor.</p><a href="https://wenli.github.io/">Personal website</a></body></html>'
HOME = ('<html><body><nav>Home About Menu Skip</nav><main><h1>Wen Li</h1><p>' + "I work on graph neural networks and scalable learning. " * 40 +
        '</p><h2>Selected Publications</h2><ul><li><a href="x.pdf">Scaling Graph Transformers to Billion Edge Graphs</a> Li, W. NeurIPS</li>'
        '<li>Li, W. "Provable Guarantees for Contrastive Representation Learning." ICML</li>'
        '<li><a href="y">Fast Sampling for Diffusion Models in Practice</a> ICLR</li><li><a href="z">Fourth Paper About Something Else Entirely</a></li>'
        '</ul></main></body></html>')


def test_page_lead_skips_nav_and_caps():
    t = fit.page_lead(HOME)
    assert t.startswith("Wen Li I work on graph") and "Menu" not in t and len(t) <= fit.HOME_MAX


def test_paper_titles_from_publications_section():
    assert fit.paper_titles(HOME) == ["Scaling Graph Transformers to Billion Edge Graphs",
                                      "Provable Guarantees for Contrastive Representation Learning",
                                      "Fast Sampling for Diffusion Models in Practice"]


def test_card_gets_homepage_text_and_papers_and_stays_small(tmp_path, monkeypatch):
    import outreach.fetch as F
    monkeypatch.setattr(fit, "DATA", tmp_path)
    monkeypatch.setattr(fit, "FIT", tmp_path / "fit")
    p = {"school": S, "name": "Wen Li", "key": list(scope.name_key("Wen Li")), "in_scope": True, "outcome": "open",
         "title": "Assistant Professor", "units": ["CS"], "profile_url": "https://cs.example.edu/people/wli",
         "gates": {"faculty": True, "young": True, "heritage": True}}
    (tmp_path / "coverage").mkdir()
    (tmp_path / "coverage" / "people.jsonl").write_text(json.dumps(p) + "\n")
    pages = {"https://cs.example.edu/people/wli": PROFILE, "https://wenli.github.io/": HOME}
    monkeypatch.setattr(F, "get", lambda u, *a, **k: pages[u])
    c = fit.build_cards(S, fetch=True)[0]
    assert c["home"].startswith("Wen Li I work on graph") and len(c["papers"]) == 3
    assert len(c["research"]) + len(c["home"]) + sum(map(len, c["papers"])) <= 900
