from clamp_page import clamp_page


def test_inside_range():
    assert clamp_page(3, 10) == 3


def test_negative_page_returns_first():
    assert clamp_page(-2, 10) == 1
