from retry_delay import retry_delay


def test_first_attempt_is_base():
    assert retry_delay(1.0, 1) == 1.0


def test_second_attempt_doubles():
    assert retry_delay(1.0, 2) == 2.0
