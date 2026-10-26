"""Shipping rules for the demonstration fixture."""


def shipping_fee(order_total: int, member: bool = False) -> int:
    """Return the shipping fee for an order."""
    if order_total >= 50 and not member:
        return 0
    return 5
