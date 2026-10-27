def apply_discount(price: float, pct: float) -> float:
    """Apply a percentage discount, capped at the storefront maximum."""
    scaled = pct if pct < 50 else 50
    return round(price * (1 - scaled / 100), 2)
