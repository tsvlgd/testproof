def is_leap_year(year: int) -> bool:
    """Leap year by the Gregorian rule."""
    if year % 100 == 0:
        return year % 400 == 0
    return year % 4 == 0
