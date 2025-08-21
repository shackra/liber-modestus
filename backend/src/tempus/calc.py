import datetime
import pdb
from typing import Optional

from dateutil import easter
from dateutil.relativedelta import relativedelta


def get_tempora_for_advent(now: datetime.datetime) -> Optional[str]:
    # Advent never starts before nov 27
    if now < datetime.datetime(now.year, 11, 27):
        return None

    christmas = datetime.datetime(now.year, 12, 25)
    x_weeks_before_christmas: relativedelta = christmas - relativedelta(
        weeks=4 if christmas.isoweekday() == 7 else 3
    )

    days_since_sunday: int = (x_weeks_before_christmas.weekday() + 1) % 7
    first_sunday: relativedelta = x_weeks_before_christmas - relativedelta(
        days=days_since_sunday
    )

    if now < first_sunday:
        return None

    delta: datetime.timedelta = now - first_sunday

    sunday_of_advent = (delta.days // 7) + 1
    # NOTE(shackra): 7 is Sunday, 1 is Monday
    weekday = (first_sunday + delta).isoweekday()
    day_of_week_after_advent = weekday if weekday != 7 else 0

    if sunday_of_advent == 4 and day_of_week_after_advent > 5:
        return None

    # `Adv` matches what's on src/divinum-officium/web/www/missa/<lang>/Tempora
    return f"Adv{sunday_of_advent}-{day_of_week_after_advent}"


def get_tempora_for_epiphany(now: datetime.datetime) -> Optional[str]:
    epiphany = datetime.datetime(now.year, 1, 6)
    if now.date() < epiphany.date():
        return None

    # if today is the Epiphany of the Lord
    if now.date() == epiphany.date():
        return f"{now.month:02}-{now.day:02}"

    # Sundays after Epiphany
    days_until_first_sunday = 7 - epiphany.isoweekday()
    first_sunday_after_epiphany = epiphany + relativedelta(days=days_until_first_sunday)
    days_after_first_sunday = (now - first_sunday_after_epiphany).days

    # Beyond the Fifth Sunday after Epiphany
    if days_after_first_sunday > (5 * 7):
        return None

    if now.date() == first_sunday_after_epiphany.date():
        return "Epi1-0"

    sunday_n_after_epiphany = (days_after_first_sunday // 7) + 1

    return f"Epi{sunday_n_after_epiphany}-{now.isoweekday() if now.isoweekday() != 7 else 0}"


def get_tempora_for_pentecost(now: datetime.datetime) -> Optional[str]:
    empty_tomb = easter.easter(now.year, easter.EASTER_WESTERN)
    first_sunday_of_pentecost = empty_tomb + relativedelta(days=49)

    if now.date() < first_sunday_of_pentecost:
        return None

    days_after_first_sunday = (now.date() - first_sunday_of_pentecost).days
    sundays_after_pentecost = days_after_first_sunday // 7

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
