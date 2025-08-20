from datetime import datetime

from tempus import get_tempora_for_advent


def test_tempora_adv_first_sunday():
    expected = "Adv1-0"
    now = datetime(2025, 11, 30)
    result = get_tempora_for_advent(now)

    assert expected == result


def test_tempora_adv_first_sunday_monday():
    expected = "Adv1-1"
    now = datetime(2025, 12, 1)
    result = get_tempora_for_advent(now)

    assert expected == result


def test_tempora_adv_first_sunday_thursday():
    expected = "Adv1-4"
    now = datetime(2025, 12, 4)
    result = get_tempora_for_advent(now)

    assert expected == result


def test_tempora_adv_second_sunday():
    expected = "Adv2-0"
    now = datetime(2025, 12, 7)
    result = get_tempora_for_advent(now)

    assert expected == result


def test_tempora_adv_second_sunday_monday():
    expected = "Adv2-1"
    now = datetime(2025, 12, 8)
    result = get_tempora_for_advent(now)

    assert expected == result


def test_tempora_adv_forth_sunday_tuesday():
    expected = "Adv4-2"
    now = datetime(2025, 12, 23)
    result = get_tempora_for_advent(now)

    assert expected == result


def test_tempora_adv_2022_forth_sunday_friday():
    expected = "Adv4-5"
    now = datetime(2022, 12, 23)
    result = get_tempora_for_advent(now)

    assert expected == result


def test_tempora_adv_2022_forth_sunday_saturday():
    expected = None
    now = datetime(2022, 12, 24)
    result = get_tempora_for_advent(now)

    assert expected == result
