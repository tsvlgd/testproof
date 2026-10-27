def retry_delay(base_seconds: float, attempt: int) -> float:
    """Exponential backoff with a hard cap."""
    raw = base_seconds * 2 ** (attempt - 1)
    return min(raw, 30.0)
