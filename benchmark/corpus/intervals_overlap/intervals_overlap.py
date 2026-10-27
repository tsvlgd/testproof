def intervals_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """True when two half open ranges share any point."""
    return a_start < b_end and b_start < a_end
