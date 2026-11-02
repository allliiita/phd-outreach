

def test_institution_name_with_comma_is_canonical():
    # 2026-11-02: UCI rows said "University of California, Irvine" and the email-domain check silently got no domains
    from outreach.config import canonical_institution, institution_domains
    assert canonical_institution("University of California, Irvine") == "University of California Irvine"
    assert institution_domains("University of California, Irvine") == ["uci.edu"]


def test_scope_rules_on_verified_titles():
    # 2026-11-02: clinical / business appointments reached the verified list via graduate-program rosters
    from outreach.verify import scope_problem
    assert scope_problem("Assistant Professor of Medicine")
    assert scope_problem("ASSOCIATE PROFESSOR | Medicine, Nephrology")
    assert scope_problem("Assistant Professor of Operations, Technology, and Information Management")
    assert not scope_problem("Associate Professor of Medicine and Biostatistics")
    assert not scope_problem("Assistant Professor of Neurosurgery, Biostatistics & Bioinformatics, Biomedical Engineering")
    assert not scope_problem("Assistant Professor of Artificial Intelligence in Radiology, Radiology")
    assert not scope_problem("Kelli Questrom Associate Professor of Information Systems + Computing & Data Sciences")
