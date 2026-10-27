from order_status import order_status


def test_open():
    assert order_status(1) == "open"


def test_unknown():
    assert order_status(9) == "unknown"
