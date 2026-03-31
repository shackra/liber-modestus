"""Tests for the horae (canonical hours) module."""

import datetime

from horae import HoraCanonica, HoraeResult, MatinsMode, get_horae

# ---------------------------------------------------------------------------
# Test location: Rome (St. Peter's Basilica)
# ---------------------------------------------------------------------------

_LAT = 41.9028
_LON = 12.4964
_TZ = "Europe/Rome"


# ---------------------------------------------------------------------------
# Equinox: day and night temporal hours should be roughly equal
# ---------------------------------------------------------------------------


def test_equinox_temporal_hours_roughly_equal():
    """On the spring equinox, day and night temporal hours should each be
    close to 60 minutes (tolerance: 5 minutes)."""
    result = get_horae(datetime.date(2025, 3, 20), _LAT, _LON, _TZ)
    five_min = datetime.timedelta(minutes=5)
    one_hour = datetime.timedelta(hours=1)

    assert abs(result.day_hour_duration - one_hour) < five_min
    assert abs(result.night_hour_duration - one_hour) < five_min
    assert result.fixed_clock_fallback is False


# ---------------------------------------------------------------------------
# Solstices: verify day/night hour asymmetry
# ---------------------------------------------------------------------------


def test_summer_solstice_day_hour_longer_than_night():
    """Near the summer solstice, daytime temporal hours should be longer
    than nighttime temporal hours."""
    result = get_horae(datetime.date(2025, 6, 21), _LAT, _LON, _TZ)
    assert result.day_hour_duration > result.night_hour_duration


def test_winter_solstice_night_hour_longer_than_day():
    """Near the winter solstice, nighttime temporal hours should be longer
    than daytime temporal hours."""
    result = get_horae(datetime.date(2025, 12, 21), _LAT, _LON, _TZ)
    assert result.night_hour_duration > result.day_hour_duration


# ---------------------------------------------------------------------------
# Chronological ordering
# ---------------------------------------------------------------------------


def test_hours_in_chronological_order():
    """All canonical hours must be sorted by start time."""
    result = get_horae(datetime.date(2025, 6, 15), _LAT, _LON, _TZ)
    starts = [h.start for h in result.hours]
    assert starts == sorted(starts)


# ---------------------------------------------------------------------------
# Prime inclusion / exclusion
# ---------------------------------------------------------------------------


def test_eight_hours_with_prime():
    """With include_prime=True, there should be 8 canonical hours and
    Prima must be among them."""
    result = get_horae(datetime.date(2025, 1, 6), _LAT, _LON, _TZ, include_prime=True)
    names = [h.name for h in result.hours]
    assert len(result.hours) == 8
    assert "Prima" in names
    assert result.include_prime is True


def test_seven_hours_without_prime():
    """With include_prime=False, there should be 7 canonical hours,
    Prima must be absent, and Laudes should absorb its slot (wider)."""
    with_prime = get_horae(
        datetime.date(2025, 1, 6), _LAT, _LON, _TZ, include_prime=True
    )
    without_prime = get_horae(
        datetime.date(2025, 1, 6), _LAT, _LON, _TZ, include_prime=False
    )

    names = [h.name for h in without_prime.hours]
    assert len(without_prime.hours) == 7
    assert "Prima" not in names
    assert without_prime.include_prime is False

    # Laudes without Prime should be wider than Laudes with Prime
    laudes_with = next(h for h in with_prime.hours if h.name == "Laudes")
    laudes_without = next(h for h in without_prime.hours if h.name == "Laudes")
    assert laudes_without.duration > laudes_with.duration

    # Laudes without Prime should end where Tertia starts
    tertia = next(h for h in without_prime.hours if h.name == "Tertia")
    assert laudes_without.end == tertia.start


# ---------------------------------------------------------------------------
# Cathedral vs. Monastic Matins
# ---------------------------------------------------------------------------


def test_cathedral_matins_one_hour_before_sunrise():
    """In cathedral mode, Matins must start exactly 1 civil hour before
    sunrise and end at sunrise."""
    result = get_horae(
        datetime.date(2025, 4, 10),
        _LAT,
        _LON,
        _TZ,
        matins_mode=MatinsMode.CATHEDRAL,
    )
    matutinum = next(h for h in result.hours if h.name == "Matutinum")
    assert matutinum.end == result.sunrise
    assert matutinum.duration == datetime.timedelta(hours=1)
    assert matutinum.start == result.sunrise - datetime.timedelta(hours=1)


def test_monastic_matins_deep_in_night():
    """In monastic mode, Matins should start at the 8th hour of the night
    (sunset + 7 * night_hour), which falls roughly around 2 AM."""
    result = get_horae(
        datetime.date(2025, 4, 10),
        _LAT,
        _LON,
        _TZ,
        matins_mode=MatinsMode.MONASTIC,
    )
    matutinum = next(h for h in result.hours if h.name == "Matutinum")

    # It should end at sunrise
    assert matutinum.end == result.sunrise

    # Start should be sunset + 7 * night_hour
    expected_start = result.sunset + 7 * result.night_hour_duration
    assert matutinum.start == expected_start

    # Roughly around 1-4 AM (sanity check)
    assert 1 <= matutinum.start.hour <= 4


# ---------------------------------------------------------------------------
# Sext should be near astronomical solar noon
# ---------------------------------------------------------------------------


def test_sext_near_solar_noon():
    """Sexta (the 6th hour) should start within 30 minutes of astronomical
    solar noon, since it marks the midpoint of daylight."""
    from astral import Observer
    from astral.sun import noon

    date = datetime.date(2025, 7, 15)
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(_TZ)
    result = get_horae(date, _LAT, _LON, _TZ)
    sexta = next(h for h in result.hours if h.name == "Sexta")

    obs = Observer(latitude=_LAT, longitude=_LON)
    solar_noon_dt = noon(obs, date=date, tzinfo=tz)

    diff = abs(sexta.start - solar_noon_dt)
    assert diff < datetime.timedelta(minutes=30)


# ---------------------------------------------------------------------------
# Daytime slot contiguity: no gaps between consecutive daytime hours
# ---------------------------------------------------------------------------


def test_daytime_slots_contiguous():
    """Each daytime hour's end must equal the next daytime hour's start,
    ensuring there are no gaps in the daytime cycle."""
    result = get_horae(datetime.date(2025, 9, 23), _LAT, _LON, _TZ)
    daytime = [h for h in result.hours if h.is_daytime]

    for i in range(len(daytime) - 1):
        assert daytime[i].end == daytime[i + 1].start, (
            f"Gap between {daytime[i].name} and {daytime[i + 1].name}: "
            f"{daytime[i].end} != {daytime[i + 1].start}"
        )

    # First daytime hour should start at sunrise, last should end at sunset
    assert daytime[0].start == result.sunrise
    assert daytime[-1].end == result.sunset


# ---------------------------------------------------------------------------
# Polar locations: fixed clock fallback
# ---------------------------------------------------------------------------

# Tromsø, Norway (69.65°N, 18.96°E)
_POLAR_LAT = 69.65
_POLAR_LON = 18.96
_POLAR_TZ = "Europe/Oslo"


def test_polar_night_falls_back_to_fixed_clock():
    """During polar night (sun never rises), the module should fall back
    to fixed clock hours (06:00 / 18:00) and set the fallback flag."""
    result = get_horae(datetime.date(2025, 12, 21), _POLAR_LAT, _POLAR_LON, _POLAR_TZ)

    assert result.fixed_clock_fallback is True
    assert result.sunrise.hour == 6 and result.sunrise.minute == 0
    assert result.sunset.hour == 18 and result.sunset.minute == 0

    # With a 12h/12h split, each temporal hour should be exactly 60 min
    assert result.day_hour_duration == datetime.timedelta(hours=1)
    assert result.night_hour_duration == datetime.timedelta(hours=1)

    # All 8 hours should be present and in chronological order
    assert len(result.hours) == 8
    starts = [h.start for h in result.hours]
    assert starts == sorted(starts)


def test_midnight_sun_falls_back_to_fixed_clock():
    """During midnight sun (sun never sets), the module should fall back
    to fixed clock hours (06:00 / 18:00) and set the fallback flag."""
    result = get_horae(datetime.date(2025, 6, 21), _POLAR_LAT, _POLAR_LON, _POLAR_TZ)

    assert result.fixed_clock_fallback is True
    assert result.sunrise.hour == 6 and result.sunrise.minute == 0
    assert result.sunset.hour == 18 and result.sunset.minute == 0

    # With a 12h/12h split, each temporal hour should be exactly 60 min
    assert result.day_hour_duration == datetime.timedelta(hours=1)
    assert result.night_hour_duration == datetime.timedelta(hours=1)

    # All 8 hours should be present and in chronological order
    assert len(result.hours) == 8
    starts = [h.start for h in result.hours]
    assert starts == sorted(starts)
