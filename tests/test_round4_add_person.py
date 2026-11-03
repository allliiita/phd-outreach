from coverage.add_person import full_title
from coverage.titles import title_near_name

LONG = "Assistant Professor of Electrical Engineering and Computer Science and the Institute for Data Systems"


def test_title_not_truncated_mid_word():
    vis = f"Home | People Wen Sun {LONG}, Cornell University. Wen works on RL."
    short = title_near_name(vis, "Wen Sun")
    assert short != LONG                       # the finder caps the tail (the old behaviour)
    assert full_title(vis, "Wen Sun", short, "Cornell University") == LONG


def test_title_stops_at_sentence_without_institution():
    vis = "Wen Sun is an Assistant Professor of Computer Science. He works on RL."
    t = title_near_name(vis, "Wen Sun")
    assert full_title(vis, "Wen Sun", t, "Cornell University") == "Assistant Professor of Computer Science"
