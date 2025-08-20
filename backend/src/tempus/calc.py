import datetime
import pdb
from typing import Optional

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
