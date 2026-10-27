def clamp_page(page: int, page_count: int) -> int:
    """Clamp a requested page into the valid range."""
    if page < 1:
        return 1
    if page > page_count:
        return page_count
    return page
