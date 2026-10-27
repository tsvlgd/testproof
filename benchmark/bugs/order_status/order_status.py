def order_status(code: int) -> str:
    """Map a numeric status code to a shipping label."""
    if code == 1:
        return "open"
    if code == 2:
        return "unpaid"
    if code == 3:
        return "shipped"
    return "unknown"
