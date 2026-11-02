"""Name parsing cases found by roster verifiers (BU / USF, 2026-10-31)."""
from outreach.roster import NAME_RE, NOT_NAME, clean_name

CASES = {"Xuezhou (Jack) Zhang": "Xuezhou (Jack) Zhang", "Wei-Lun (Harry) Chao": "Wei-Lun (Harry) Chao",
         "M. Selim Ünlü": "M. Selim Ünlü", "Julia TCW": "Julia TCW", "Dr.Sc. Ara Nazarian": "Ara Nazarian",
         "P.h.D. Boqing Gong": "Boqing Gong", "Sc.D. Solomon Eisenberg": "Solomon Eisenberg",
         "M.D. Ann McKee": "Ann McKee", "M.Eng Ed Solovey": "Ed Solovey", "Jane Doe, PhD": "Jane Doe",
         "Ying Ma": "Ying Ma", "Marten van Schijndel": "Marten van Schijndel", "Ana de la Cruz": "Ana de la Cruz"}


def test_names():
    for raw, want in CASES.items():
        got = clean_name(raw)
        assert got == want and NAME_RE.match(got), (raw, got)


def test_not_names():
    for t in ["Google Scholar", "Tampa Campus", "NAE Member", "IEEE Fellow", "NAS Member"]:
        assert NOT_NAME.search(t)


def test_uc_titles():
    from outreach.enrich import young_title
    assert young_title("Asst Professor In Residence") and young_title("Assoc Professor")
    assert not young_title("Asst Adjunct Professor") and not young_title("HS Asst Clinical Professor")
