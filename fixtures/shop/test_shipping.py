"""A deliberately weak test suite used by the TestProof demo."""

from shipping import shipping_fee


def test_free_shipping() -> None:
    assert shipping_fee(100) == 0


def test_paid_shipping() -> None:
    assert shipping_fee(10) == 5
