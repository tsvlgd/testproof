from grade_band import grade_band


def test_fail_band():
    assert grade_band(30) == "F"


def test_top_band():
    assert grade_band(95) == "A"
