from intervals_overlap import intervals_overlap


def test_disjoint():
    assert intervals_overlap(0, 2, 5, 8) is False


def test_contained():
    assert intervals_overlap(0, 10, 2, 4) is True
