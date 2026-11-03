import json
import pytest
from pathlib import Path
from outreach.enrich import young_title

@pytest.mark.parametrize("t", ["Dutton-Ducoffe Professor and Associate Professor", "Dutton-Ducoffe Endowed Professor",
                               "Professor and Chair", "Distinguished Professor", "Smith Chair, Associate Professor"])
def test_senior_not_young(t):
    assert not young_title(t)

@pytest.mark.parametrize("t", ["Assistant Professor", "Associate Professor", "Associate Professor and Director of X",
                               "Assistant Professor of Computer Science", "Associate Professor and Associate Chair"])
def test_ranks_stay_young(t):
    assert young_title(t)

def test_real_roster_ducoffe_rows_not_young():
    rows = [json.loads(l) for p in Path("data/roster").glob("*.jsonl") for l in p.read_text().splitlines() if "Ducoffe" in l]
    assert rows and not any(young_title(r["title_on_roster"]) for r in rows)
