def grade_band(score: int) -> str:
    """Return the letter band for a score out of 100."""
    if score >= 90:
        return "A"
    if score >= 85:
        return "B"
    if score >= 60:
        return "C"
    return "F"
