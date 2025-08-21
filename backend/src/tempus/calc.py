import calendar
import datetime
import pdb
from typing import Optional

from dateutil import easter
from dateutil.relativedelta import relativedelta


def get_absolute_date_septuagesima_sunday(year: int) -> datetime.date:
    # TODO(shackra): on 4098 AD, raise from the death and
    # TODO(shackra): update this code to work with years after 4099
    if year < 1583 or year > 4099:
        raise ValueError(f"{year} cannot be before 1583 or after 4099")

    septuagesima_sunday = easter.easter(year, easter.EASTER_WESTERN) - relativedelta(
        days=63
    )

    return septuagesima_sunday


def get_absolute_date_23_sunday_after_pent(year: int) -> datetime.date:
    if year < 1583 or year > 4099:
        raise ValueError(f"{year} cannot be before 1583 or after 4099")

    empty_tomb = easter.easter(year, easter.EASTER_WESTERN)
    first_sunday_of_pentecost = empty_tomb + relativedelta(days=49)

    return first_sunday_of_pentecost + relativedelta(weeks=22)


def get_absolute_date_first_sunday_of_advent(year: int) -> datetime.date:
    # TODO(shackra): on 4098 AD, raise from the death and
    # TODO(shackra): update this code to work with years after 4099
    if year < 1583 or year > 4099:
        raise ValueError(f"{year} cannot be before 1583 or after 4099")

    christmas = datetime.datetime(year, 12, 25)
    x_weeks_before_christmas: relativedelta = christmas - relativedelta(
        weeks=4 if christmas.isoweekday() == 7 else 3
    )

    days_since_sunday: int = (x_weeks_before_christmas.weekday() + 1) % 7
    first_sunday: relativedelta = x_weeks_before_christmas - relativedelta(
        days=days_since_sunday
    )

    return first_sunday.date()


def get_amount_sundays_after_epiphany(year: int) -> int:
    epiphany = datetime.date(year, 1, 6)
    septuagesima_sunday = get_absolute_date_septuagesima_sunday(year)

    days = (septuagesima_sunday - epiphany).days

    return days // 7


def get_amount_sundays_between_pent23_advent(year: int) -> int:
    advent = get_absolute_date_first_sunday_of_advent(year)
    pent23 = get_absolute_date_23_sunday_after_pent(year)

    return ((advent - pent23).days // 7) - 2  # excludes Pent 23 and Advent


def get_tempora_for_advent(now: datetime.datetime) -> Optional[str]:
    # Advent never starts before nov 27
    if now < datetime.datetime(now.year, 11, 27):
        return None

    first_sunday = get_absolute_date_first_sunday_of_advent(now.year)

    if now.date() < first_sunday:
        return None

    delta: datetime.timedelta = now.date() - first_sunday

    sunday_of_advent = (delta.days // 7) + 1
    # NOTE(shackra): 7 is Sunday, 1 is Monday
    weekday = (first_sunday + delta).isoweekday()
    day_of_week_after_advent = weekday if weekday != 7 else 0

    if sunday_of_advent == 4 and day_of_week_after_advent > 5:
        return None

    if now >= datetime.datetime(now.year, 12, 24):
        return None

    # `Adv` matches what's on src/divinum-officium/web/www/missa/<lang>/Tempora
    return f"Adv{sunday_of_advent}-{day_of_week_after_advent}"


def get_tempora_for_epiphany(now: datetime.datetime) -> Optional[str]:
    epiphany = datetime.datetime(now.year, 1, 6)
    septuagesima = get_absolute_date_septuagesima_sunday(now.year)

    if now.date() < epiphany.date() or now.date() >= septuagesima:
        return None

    # if today is the Epiphany of the Lord
    if now.date() == epiphany.date():
        return f"{now.month:02}-{now.day:02}"

    # Sundays after Epiphany
    days_until_first_sunday = 7 - epiphany.isoweekday()
    first_sunday_after_epiphany = epiphany + relativedelta(days=days_until_first_sunday)
    days_after_first_sunday = (now - first_sunday_after_epiphany).days

    sunday_n_after_epiphany = (days_after_first_sunday // 7) + 1

    return f"Epi{sunday_n_after_epiphany}-{now.isoweekday() if now.isoweekday() != 7 else 0}"


def get_tempora_for_pentecost(now: datetime.datetime) -> Optional[str]:
    empty_tomb = easter.easter(now.year, easter.EASTER_WESTERN)
    first_sunday_of_pentecost = empty_tomb + relativedelta(days=49)
    advent = get_absolute_date_first_sunday_of_advent(now.year)

    if now.date() < first_sunday_of_pentecost or now.date() >= advent:
        return None

    days_after_first_sunday = (now.date() - first_sunday_of_pentecost).days
    sundays_after_pentecost = days_after_first_sunday // 7

    # keep one slot for Sunday XXIV
    sundays_before_advent = get_amount_sundays_between_pent23_advent(now.year) - 1
    sunday_after_epiphany = sundays_after_pentecost - (
        20 if calendar.isleap(now.year) else 19
    )
    if (
        now.isoweekday() == 7
        and sundays_before_advent >= 1
        and sundays_after_pentecost > 23
        and sunday_after_epiphany <= 6
    ):
        return f"Epi{sunday_after_epiphany}-0"

    if sundays_after_pentecost > 24:
        sundays_after_pentecost = 24

    return f"Pent{sundays_after_pentecost:02}-{now.isoweekday() if now.isoweekday() != 7 else 0}"


def get_tempora_for_pasch(now: datetime.datetime) -> Optional[str]:
    empty_tomb = easter.easter(now.year, easter.EASTER_WESTERN)
    days_after_resurrection_sunday = (now.date() - empty_tomb).days

    if now.date() < empty_tomb or days_after_resurrection_sunday > ((8 * 7) - 1):
        return None

    sundays_after_resurrection_sunday = days_after_resurrection_sunday // 7

    return f"Pasc{sundays_after_resurrection_sunday}-{now.isoweekday() if now.isoweekday() != 7 else 0}"


def get_tempora_for_lent(now: datetime.datetime) -> Optional[str]:
    first_sunday_of_lent = easter.easter(
        now.year, easter.EASTER_WESTERN
    ) - relativedelta(days=42)

    if now.date() < first_sunday_of_lent:
        return None

    days_after_first_sunday = (now.date() - first_sunday_of_lent).days
    sundays_after_first_sunday_of_lent = (days_after_first_sunday // 7) + 1

    if sundays_after_first_sunday_of_lent > 6:
        return None  # the 7th Sunday is Easter!

    return f"Quad{sundays_after_first_sunday_of_lent}-{now.isoweekday() if now.isoweekday() != 7 else 0}"


def get_tempora_for_quadp(now: datetime.datetime) -> Optional[str]:
    septuagesima_sunday = easter.easter(
        now.year, easter.EASTER_WESTERN
    ) - relativedelta(days=63)
    days_after_septuagesima_sunday = (now.date() - septuagesima_sunday).days

    if now.date() < septuagesima_sunday or days_after_septuagesima_sunday > (3 * 7 - 1):
        return None

    sundays_after_septuagesima_sunday = (days_after_septuagesima_sunday // 7) + 1

    return f"Quadp{sundays_after_septuagesima_sunday}-{now.isoweekday() if now.isoweekday() != 7 else 0}"
