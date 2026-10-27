def parse_seconds(spec: str) -> int:
    """Parse a duration like 30s, 5m, or 2h into seconds."""
    if spec.endswith("s"):
        return int(spec[:-1])
    if spec.endswith("m"):
        return int(spec[:-1]) * 60
    if spec.endswith("h"):
        return int(spec[:-1]) * 3600
    raise ValueError(f"unknown unit in {spec!r}")
