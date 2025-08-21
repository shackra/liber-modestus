from datetime import datetime

from tempus import (
    get_tempora_for_advent,
    get_tempora_for_epiphany,
    get_tempora_for_lent,
    get_tempora_for_pasch,
    get_tempora_for_pentecost,
    get_tempora_for_quadp,
)


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


def test_tempora_epi_before_day():
    expected = None
    now = datetime(2025, 1, 5)

    result = get_tempora_for_epiphany(now)

    assert expected == result


def test_tempora_epi_today_day():
    expected = "01-06"
    now = datetime(2025, 1, 6, 19, 55, 16)

    result = get_tempora_for_epiphany(now)

    assert expected == result


def test_tempora_epi_first_sunday():
    expected = "Epi1-0"
    now = datetime(2025, 1, 12)

    result = get_tempora_for_epiphany(now)

    assert expected == result


def test_tempora_epi_second_sunday():
    expected = "Epi2-0"
    now = datetime(2025, 1, 19)

    result = get_tempora_for_epiphany(now)

    assert expected == result


def test_tempora_epi_third_sunday():
    expected = "Epi3-0"
    now = datetime(2025, 1, 26)

    result = get_tempora_for_epiphany(now)

    assert expected == result


def test_tempora_epi_forth_sunday():
    expected = "Epi4-0"
    now = datetime(2025, 2, 2)

    result = get_tempora_for_epiphany(now)

    assert expected == result


def test_tempora_epi_fifth_sunday():
    expected = "Epi5-0"
    now = datetime(2025, 2, 9)

    result = get_tempora_for_epiphany(now)

    assert expected == result


def test_tempora_pent_first_sunday():
    expected = "Pent01-0"
    now = datetime(2025, 6, 15)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_first_sunday_feria_2():
    expected = "Pent01-1"
    now = datetime(2025, 6, 16)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_23():
    expected = "Pent23-0"
    now = datetime(2025, 11, 16)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_23_feria_2():
    expected = "Pent23-1"
    now = datetime(2025, 11, 17)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_24():
    expected = "Pent24-0"
    now = datetime(2025, 11, 23)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_24_feria_2():
    expected = "Pent24-1"
    now = datetime(2025, 11, 24)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_after_advent_should_return_none():
    expected = None
    now = datetime(2025, 12, 25)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_24_2024():
    expected = "Pent24-0"
    now = datetime(2024, 11, 24)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_iv_epi_2024():
    expected = "Epi4-0"
    now = datetime(2024, 11, 3)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_v_epi_2024():
    expected = "Epi5-0"
    now = datetime(2024, 11, 10)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_vi_epi_2024():
    expected = "Epi6-0"
    now = datetime(2024, 11, 17)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_v_epi_2026():
    expected = "Epi5-0"
    now = datetime(2026, 11, 8)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pent_sunday_vi_epi_2026():
    expected = "Epi6-0"
    now = datetime(2026, 11, 15)

    result = get_tempora_for_pentecost(now)

    assert expected == result


def test_tempora_pasc():
    expected = "Pasc0-0"
    now = datetime(2025, 4, 20)

    result = get_tempora_for_pasch(now)

    assert expected == result


def test_tempora_pasc_second_sunday():
    expected = "Pasc1-0"
    now = datetime(2025, 4, 27)

    result = get_tempora_for_pasch(now)

    assert expected == result


def test_tempora_pasc_third_sunday():
    expected = "Pasc2-0"
    now = datetime(2025, 5, 4)

    result = get_tempora_for_pasch(now)

    assert expected == result


def test_tempora_pasc_fifth_sunday():
    expected = "Pasc5-0"
    now = datetime(2025, 5, 25)

    result = get_tempora_for_pasch(now)

    assert expected == result


def test_tempora_pasc_sixth_sunday():
    expected = "Pasc6-0"
    now = datetime(2025, 6, 1)

    result = get_tempora_for_pasch(now)

    assert expected == result


def test_tempora_pent():
    expected = "Pasc7-0"
    now = datetime(2025, 6, 8)

    result = get_tempora_for_pasch(now)

    assert expected == result


def test_tempora_first_sunday_of_lent():
    expected = "Quad1-0"
    now = datetime(2025, 3, 9)

    result = get_tempora_for_lent(now)

    assert expected == result


def test_tempora_lent_palm_sunday():
    expected = "Quad6-0"
    now = datetime(2025, 4, 13)

    result = get_tempora_for_lent(now)

    assert expected == result


def test_tempora_lent_pasc_none():
    expected = None
    now = datetime(2025, 4, 20)

    result = get_tempora_for_lent(now)

    assert expected == result


def test_tempora_quadp_sunday():
    expected = "Quadp1-0"
    now = datetime(2025, 2, 16)

    result = get_tempora_for_quadp(now)

    assert expected == result


def test_tempora_quadp_sunday_3_saturday_after_ash_wednesday():
    expected = "Quadp3-6"
    now = datetime(2025, 3, 8)

    result = get_tempora_for_quadp(now)

    assert expected == result
