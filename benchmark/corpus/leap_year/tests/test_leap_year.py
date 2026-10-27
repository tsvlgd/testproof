from leap_year import is_leap_year


def test_regular_leap():
    assert is_leap_year(2024) is True


def test_regular_common():
    assert is_leap_year(2023) is False
