from coupon_discount import apply_discount


def test_small_discount():
    assert apply_discount(100.0, 10.0) == 90.0


def test_no_discount():
    assert apply_discount(40.0, 0.0) == 40.0
