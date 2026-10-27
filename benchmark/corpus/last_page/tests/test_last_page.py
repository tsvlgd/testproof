from last_page import last_page


def test_partial_last_page():
    assert last_page(31, 10) == 4


def test_small_listing():
    assert last_page(7, 10) == 1
