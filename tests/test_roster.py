

def test_institution_name_with_comma_is_canonical():
    # 2026-11-02: UCI rows said "University of California, Irvine" and the email-domain check silently got no domains
    from outreach.config import canonical_institution, institution_domains
    assert canonical_institution("University of California, Irvine") == "University of California Irvine"
    assert institution_domains("University of California, Irvine") == ["uci.edu"]
