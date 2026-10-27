from mask_card import mask_card


def test_long_card_is_masked():
    masked = mask_card("1234 5678 9012 3456")
    assert masked.endswith("3456")
    assert masked[:5] == "*****"


def test_short_card_is_hidden():
    assert mask_card("123") == "***"
