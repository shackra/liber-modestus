import datetime
import os

import captator


def test_get_date_to_liturgical_calendar():
    expected = "01-06"
    now = datetime.datetime(2025, 1, 6)

    result = captator.get_date_to_liturgical_calendar(now)

    assert expected == result


def test_get_divinum_officium_files_path():
    envvar_name = "TEST_ONLY_DO_FILES_PATH"
    FILES_LOCATION = os.getenv(envvar_name)
    if FILES_LOCATION is None:
        raise ValueError(f"{envvar_name} not set, this is required for this test")

    location = captator.get_divinum_officium_files_path()

    assert FILES_LOCATION == location


def test_get_propers_for_christmas():
    now = datetime.datetime(2025, 12, 25)

    found = captator.get_propers_for_date(now, "es")

    assert len(found["sancti"]) > 0
    assert len(found["tempora"]) == 0
    assert len(found["sancti_other"]) > 0
    assert len(found["tempora_other"]) == 0


def test_get_propers_for_feria_iv_after_ash_wednesday():
    now = datetime.datetime(2025, 7, 3)  # Comm: St. Thomas Aquinas

    found = captator.get_propers_for_date(now, "es")

    assert len(found["sancti"]) > 0
    assert len(found["tempora"]) > 0
    assert len(found["sancti_other"]) > 0
    assert len(found["tempora_other"]) > 0
