from check_password import check_password


def test_accepts_good_password():
    assert check_password("Passw0rd99") is True


def test_rejects_short():
    assert check_password("aB1") is False
