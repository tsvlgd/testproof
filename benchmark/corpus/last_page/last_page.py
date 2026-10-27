def last_page(item_count: int, page_size: int) -> int:
    """Return the number of the final page for a listing."""
    if item_count <= 0:
        return 1
    return (item_count + page_size - 1) // page_size
