from parse_seconds import parse_seconds


def test_seconds():
    assert parse_seconds("45s") == 45


def test_minutes():
    assert parse_seconds("3m") == 180
