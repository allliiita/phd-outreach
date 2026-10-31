"""Name parsing cases found by roster verifiers (BU / USF, 2026-10-31)."""
from outreach.roster import NAME_RE, NOT_NAME, clean_name

CASES = {"Xuezhou (Jack) Zhang": "Xuezhou (Jack) Zhang", "Wei-Lun (Harry) Chao": "Wei-Lun (Harry) Chao",
         "M. Selim Ünlü": "M. Selim Ünlü", "Julia TCW": "Julia TCW", "Dr.Sc. Ara Nazarian": "Ara Nazarian",
         "P.h.D. Boqing Gong": "Boqing Gong", "Sc.D. Solomon Eisenberg": "Solomon Eisenberg",
         "M.D. Ann McKee": "Ann McKee", "M.Eng Ed Solovey": "Ed Solovey", "Jane Doe, PhD": "Jane Doe",
         "Ying Ma": "Ying Ma"}


def test_names():
    for raw, want in CASES.items():
        got = clean_name(raw)
        assert got == want and NAME_RE.match(got), (raw, got)


def test_not_names():
    for t in ["Google Scholar", "Tampa Campus"]:
        assert NOT_NAME.search(t)
