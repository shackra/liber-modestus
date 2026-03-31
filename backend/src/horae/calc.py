"""Canonical hours calculator using temporal (unequal) hours.

Sunrise and sunset times are obtained from the ``astral`` library, which
implements the NOAA solar position equations.

The traditional Roman system divides daytime (sunrise to sunset) and
nighttime (sunset to next sunrise) each into 12 equal *temporal* hours
whose absolute length varies with the season and geographic location.
"""

from __future__ import annotations

import datetime
import enum
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import sunrise as astral_sunrise
from astral.sun import sunset as astral_sunset

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


class MatinsMode(enum.Enum):
    """How to place Matins (Matutinum) in the daily cycle.

    CATHEDRAL -- Matins begins 1 civil hour before sunrise (parish use).
    MONASTIC  -- Matins begins at the 8th hour of the night (~2 AM),
                 following the Benedictine tradition.
    """

    CATHEDRAL = "cathedral"
    MONASTIC = "monastic"


@dataclass(frozen=True)
class HoraCanonica:
    """A single canonical hour with its computed time slot."""

    name: str
    """Latin name: Matutinum, Laudes, Prima, Tertia, Sexta, Nona,
    Vesperae, Completorium."""

    start: datetime.datetime
    """Timezone-aware start of this hour's slot."""

    end: datetime.datetime
    """Timezone-aware end of this hour's slot."""

    duration: datetime.timedelta
    """*end* minus *start*."""

    roman_hour: int
    """Which Roman temporal hour marks the start of this slot (1--12).
    For Matutinum in cathedral mode, 0 is used as a sentinel."""

    is_daytime: bool
    """True when the slot falls in the daytime period (sunrise--sunset)."""


@dataclass(frozen=True)
class HoraeResult:
    """All canonical hours for a given date, location, and configuration."""

    date: datetime.date
    latitude: float
    longitude: float
    sunrise: datetime.datetime
    sunset: datetime.datetime
    hours: tuple[HoraCanonica, ...]
    day_hour_duration: datetime.timedelta
    night_hour_duration: datetime.timedelta
    include_prime: bool
    matins_mode: MatinsMode
    fixed_clock_fallback: bool
    """True when the sun never rises or never sets at the given location
    and date (polar night or midnight sun).  In that case, nominal times
    of 06:00 (sunrise) and 18:00 (sunset) in the requested timezone are
    used, following the convention adopted by religious orders in extreme
    latitudes."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sun_times(
    date: datetime.date,
    latitude: float,
    longitude: float,
    tz: ZoneInfo,
) -> tuple[datetime.datetime, datetime.datetime, bool]:
    """Return *(sunrise, sunset, is_fallback)* as timezone-aware datetimes.

    When the sun never rises or never sets (polar night / midnight sun),
    nominal times of 06:00 and 18:00 in the requested timezone are
    returned and *is_fallback* is ``True``.
    """
    observer = Observer(latitude=latitude, longitude=longitude)
    try:
        rise = astral_sunrise(observer, date=date, tzinfo=tz)
        sset = astral_sunset(observer, date=date, tzinfo=tz)
        return rise, sset, False
    except ValueError:
        rise = datetime.datetime(date.year, date.month, date.day, 6, 0, 0, tzinfo=tz)
        sset = datetime.datetime(date.year, date.month, date.day, 18, 0, 0, tzinfo=tz)
        return rise, sset, True


def _build_hora(
    name: str,
    start: datetime.datetime,
    end: datetime.datetime,
    roman_hour: int,
    is_daytime: bool,
) -> HoraCanonica:
    return HoraCanonica(
        name=name,
        start=start,
        end=end,
        duration=end - start,
        roman_hour=roman_hour,
        is_daytime=is_daytime,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_horae(
    date: datetime.date,
    latitude: float,
    longitude: float,
    timezone: str,
    include_prime: bool = True,
    matins_mode: MatinsMode = MatinsMode.CATHEDRAL,
) -> HoraeResult:
    """Calculate the canonical hours for *date* at *(latitude, longitude)*.

    Parameters
    ----------
    date:
        The calendar date.
    latitude, longitude:
        Geographic coordinates in decimal degrees (north / east positive).
    timezone:
        IANA timezone name, e.g. ``"Europe/Rome"`` or ``"America/Chicago"``.
    include_prime:
        If ``True`` (default) the hour of *Prima* is included.  Set to
        ``False`` for the post-Vatican II arrangement that suppressed Prime.
    matins_mode:
        Controls when Matins (Matutinum) is placed.  See :class:`MatinsMode`.

    Returns
    -------
    HoraeResult
        Immutable result containing all computed hour slots and metadata.
    """
    tz = ZoneInfo(timezone)

    # --- sunrise / sunset for the requested day --------------------------
    sunrise, sunset, fallback_today = _sun_times(date, latitude, longitude, tz)

    # --- sunrise for the *next* day (needed for night-hour duration) -----
    next_day = date + datetime.timedelta(days=1)
    next_sunrise, _, fallback_next = _sun_times(next_day, latitude, longitude, tz)

    fixed_clock_fallback = fallback_today or fallback_next

    # --- temporal hour durations -----------------------------------------
    day_duration = sunset - sunrise
    night_duration = next_sunrise - sunset
    day_hour = day_duration / 12
    night_hour = night_duration / 12

    # --- build the daytime hour boundaries -------------------------------
    #
    #  Laudes        : sunrise                    .. sunrise + 1*day_hour
    #  Prima         : sunrise + 1*day_hour       .. sunrise + 3*day_hour
    #  Tertia        : sunrise + 3*day_hour       .. sunrise + 6*day_hour
    #  Sexta         : sunrise + 6*day_hour       .. sunrise + 9*day_hour
    #  Nona          : sunrise + 9*day_hour       .. sunset
    #
    # If Prime is excluded, Laudes absorbs its slot:
    #  Laudes (wide) : sunrise                    .. sunrise + 3*day_hour

    laudes_start = sunrise
    prima_start = sunrise + day_hour
    tertia_start = sunrise + 3 * day_hour
    sexta_start = sunrise + 6 * day_hour
    nona_start = sunrise + 9 * day_hour
    nona_end = sunset

    # --- nighttime hour boundaries ---------------------------------------
    vesperae_start = sunset
    vesperae_end = sunset + night_hour
    completorium_start = vesperae_end

    # --- Matins placement ------------------------------------------------
    if matins_mode is MatinsMode.MONASTIC:
        matutinum_start = sunset + 7 * night_hour
        matutinum_roman = 8
    else:  # CATHEDRAL
        matutinum_start = sunrise - datetime.timedelta(hours=1)
        matutinum_roman = 0  # sentinel: not a Roman temporal hour

    matutinum_end = sunrise  # Matins always ends at sunrise (start of Lauds)

    # Compline ends when Matins begins.
    # For the *current* day's Compline, "next Matins" is technically the
    # next occurrence.  In monastic mode that is later the same night; in
    # cathedral mode it is 1 h before the *next* sunrise.
    if matins_mode is MatinsMode.MONASTIC:
        completorium_end = matutinum_start
    else:
        completorium_end = next_sunrise - datetime.timedelta(hours=1)

    # --- assemble hours --------------------------------------------------
    hours: list[HoraCanonica] = []

    hours.append(
        _build_hora("Matutinum", matutinum_start, matutinum_end, matutinum_roman, False)
    )

    if include_prime:
        hours.append(_build_hora("Laudes", laudes_start, prima_start, 1, True))
        hours.append(_build_hora("Prima", prima_start, tertia_start, 1, True))
    else:
        # Laudes absorbs Prima's slot
        hours.append(_build_hora("Laudes", laudes_start, tertia_start, 1, True))

    hours.append(_build_hora("Tertia", tertia_start, sexta_start, 3, True))
    hours.append(_build_hora("Sexta", sexta_start, nona_start, 6, True))
    hours.append(_build_hora("Nona", nona_start, nona_end, 9, True))
    hours.append(_build_hora("Vesperae", vesperae_start, vesperae_end, 12, False))
    hours.append(
        _build_hora("Completorium", completorium_start, completorium_end, 1, False)
    )

    # Sort chronologically by start time
    hours.sort(key=lambda h: h.start)

    return HoraeResult(
        date=date,
        latitude=latitude,
        longitude=longitude,
        sunrise=sunrise,
        sunset=sunset,
        hours=tuple(hours),
        day_hour_duration=day_hour,
        night_hour_duration=night_hour,
        include_prime=include_prime,
        matins_mode=matins_mode,
        fixed_clock_fallback=fixed_clock_fallback,
    )
