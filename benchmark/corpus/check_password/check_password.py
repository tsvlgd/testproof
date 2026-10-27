def check_password(password: str) -> bool:
    """Policy: at least eight characters with a digit and an uppercase letter."""
    if len(password) < 8:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_upper = any(c.isupper() for c in password)
    return has_digit and has_upper
