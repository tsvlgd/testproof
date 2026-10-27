def mask_card(number: str) -> str:
    """Mask all but the last digits of a payment card."""
    digits = number.replace(" ", "")
    visible = 4
    if len(digits) <= visible:
        return "*" * len(digits)
    return "*" * (len(digits) - visible) + digits[-visible:]
