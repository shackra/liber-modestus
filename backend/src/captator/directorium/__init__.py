"""Directorium: liturgical calendar engine for the traditional Roman Missa.

Given a date and a ``MissalConfig``, determines which Mass propers to
use by resolving the temporal cycle, sanctoral calendar, transfers,
and occurrence precedence rules.

Usage::

    from datetime import date
    from captator.resolver import MissalConfig, Rubric
    from captator.directorium import get_mass_propers, MassDay

    config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
    day = get_mass_propers(date(2025, 12, 25), config,
                           tabulae_path="path/to/Tabulae",
                           missa_path="path/to/missa/Latin")
    print(day.winner_file)        # 'Sancti/12-25'
    print(day.resolved_document)  # fully resolved Document AST
"""

from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dateutil.easter import EASTER_WESTERN, easter

from captator.parser import Document, parse_file
from captator.resolver import MissalConfig, Rubric, resolve
from captator.resolver.config import OrderVariant

from .occurrence import OccurrenceResult, resolve_occurrence
from .tables import (
    KalendarEntry,
    VersionConfig,
    _collect_version_stems,
    load_data_config,
    load_kalendar_merged,
    load_tempora_merged,
    load_transfer,
)

# ---------------------------------------------------------------------------
# Version name mapping: MissalConfig.Rubric -> data.txt version key
# ---------------------------------------------------------------------------

_RUBRIC_TO_VERSION: dict[Rubric, str] = {
    Rubric.TRIDENT_1570: "Tridentine - 1570",
    Rubric.TRIDENT_1910: "Tridentine - 1906",
    Rubric.TRIDENT_1930: "Divino Afflatu - 1939",
    Rubric.RUBRICAE_1955: "Reduced - 1955",
    Rubric.RUBRICAE_1960: "Rubrics 1960 - 1960",
}


def _get_version_key(config: MissalConfig) -> str:
    """Map a MissalConfig to the data.txt version name."""
    base = _RUBRIC_TO_VERSION.get(config.rubric, "Rubrics 1960 - 1960")

    # Handle monastic/order variants
    match config.order:
        case OrderVariant.MONASTIC:
            if config.rubric in (Rubric.RUBRICAE_1960, Rubric.RUBRICAE_1955):
                return "Monastic - 1963"
            return "Monastic Divino 1930"
        case OrderVariant.DOMINICAN:
            return "Ordo Praedicatorum - 1962"
        case OrderVariant.CISTERCIAN:
            return "Monastic Tridentinum Cisterciensis 1951"
        case _:
            return base


# ---------------------------------------------------------------------------
# Temporal cycle: date -> Tempora ID
# ---------------------------------------------------------------------------


def _get_tempora_id(dt: datetime.date, year_easter: datetime.date) -> Optional[str]:
    """Compute the Tempora ID for a given date.

    Returns the base temporal ID (before Tempora table remapping),
    e.g., 'Adv1-0', 'Quad6-4', 'Pasc0-0', 'Pent14-3'.

    Returns None for dates in the Sanctoral-only periods
    (parts of Christmastide, etc.).
    """
    year = dt.year

    # Weekday: 0=Sunday, 1=Monday, ..., 6=Saturday
    dow = dt.isoweekday()
    weekday = 0 if dow == 7 else dow

    # Key dates for this year
    epiphany = datetime.date(year, 1, 6)
    septuagesima = year_easter - datetime.timedelta(days=63)
    lent_start = year_easter - datetime.timedelta(days=42)  # first Sunday of Lent
    pentecost = year_easter + datetime.timedelta(days=49)

    # Advent of the PREVIOUS year might still apply in early January
    # But we only handle within the year for simplicity

    # --- Advent ---
    christmas = datetime.date(year, 12, 25)
    xmas_dow = christmas.isoweekday()
    weeks_back = 4 if xmas_dow == 7 else 3
    ref = christmas - datetime.timedelta(weeks=weeks_back)
    ref_days_since_sun = (ref.weekday() + 1) % 7
    advent1 = ref - datetime.timedelta(days=ref_days_since_sun)

    if dt >= advent1 and dt < datetime.date(year, 12, 24):
        delta = (dt - advent1).days
        week = (delta // 7) + 1
        return f"Adv{week}-{weekday}"

    # --- Christmas Eve and Christmastide ---
    if dt.month == 12 and dt.day >= 24:
        day_in_octave = dt.day
        if dt.day == 24:
            return None  # Vigilia Nativitatis is in Sancti/
        if dt.day == 25:
            return None  # Christmas is in Sancti/
        # Dec 26-31: Natxx
        return f"Nat{dt.day:02d}"

    # --- Christmastide January 1-5 ---
    if dt.month == 1 and dt.day <= 5:
        return f"Nat{dt.day:02d}"

    # --- Epiphany season ---
    if dt == epiphany:
        return None  # Epiphany is in Sancti/01-06

    if dt > epiphany and dt < septuagesima:
        days_until_first_sun = 7 - epiphany.isoweekday()
        first_sun = epiphany + datetime.timedelta(days=days_until_first_sun)
        if dt < first_sun:
            # Days between Epiphany and its first Sunday
            delta = (dt - epiphany).days
            return f"Epi1-{weekday}"
        days_after = (dt - first_sun).days
        week = (days_after // 7) + 1
        return f"Epi{week}-{weekday}"

    # --- Pre-Lent (Septuagesima) ---
    if dt >= septuagesima and dt < lent_start:
        delta = (dt - septuagesima).days
        week = (delta // 7) + 1
        return f"Quadp{week}-{weekday}"

    # --- Lent (Quadragesima) ---
    if dt >= lent_start and dt < year_easter:
        delta = (dt - lent_start).days
        week = (delta // 7) + 1
        return f"Quad{week}-{weekday}"

    # --- Paschaltide ---
    if dt >= year_easter and dt < pentecost + datetime.timedelta(days=7):
        delta = (dt - year_easter).days
        week = delta // 7
        return f"Pasc{week}-{weekday}"

    # --- Pentecost season ---
    if dt >= pentecost and dt < advent1:
        delta = (dt - pentecost).days
        week = delta // 7

        # Cap at 24 (last Sunday before Advent is always Pent24)
        if week > 24:
            week = 24

        # Transferred Epiphany Sundays logic
        if weekday == 0 and week > 23:
            # Check if there's room for transferred Epiphany Sundays
            sundays_to_advent = (advent1 - dt).days // 7
            epi_sundays = _count_epiphany_sundays(year, year_easter)
            max_epi = 6
            available_epi = max_epi - epi_sundays
            if available_epi > 0 and sundays_to_advent >= 1:
                epi_week = week - (20 if calendar.isleap(year) else 19)
                if 1 <= epi_week <= 6:
                    return f"Epi{epi_week}-0"

        return f"Pent{week:02d}-{weekday}"

    return None


def _count_epiphany_sundays(year: int, year_easter: datetime.date) -> int:
    """Count how many Sundays fall between Epiphany and Septuagesima."""
    epiphany = datetime.date(year, 1, 6)
    septuagesima = year_easter - datetime.timedelta(days=63)
    return (septuagesima - epiphany).days // 7


def _get_tempora_rank(tempora_id: Optional[str]) -> float:
    """Estimate the rank of a temporal day from its ID.

    This is a simplified heuristic. The actual rank comes from the
    ``[Rank]`` section of the parsed file, but we need an estimate
    for occurrence resolution before loading the file.
    """
    if tempora_id is None:
        return 0.0

    is_sunday = tempora_id.endswith("-0")

    # Triduum and Easter Week
    if tempora_id.startswith("Quad6-") and not tempora_id.endswith("-0"):
        day = int(tempora_id[-1])
        if day >= 4:  # Holy Thursday, Good Friday, Holy Saturday
            return 7.0

    if tempora_id.startswith("Pasc0-"):
        return 7.0  # Easter Week

    if tempora_id == "Pasc7-0":
        return 7.0  # Pentecost Sunday

    # Advent Sundays
    if tempora_id.startswith("Adv") and is_sunday:
        return 5.0  # I classis Sundays

    # Septuagesima Sundays (check before Quad to avoid Quadp matching Quad)
    if tempora_id.startswith("Quadp") and is_sunday:
        return 5.0

    # Lent Sundays
    if tempora_id.startswith("Quad") and is_sunday:
        week = int(tempora_id[4])
        if week == 6:
            return 7.0  # Palm Sunday
        return 5.0

    # Pentecost Sundays
    if tempora_id.startswith("Pent") and is_sunday:
        return 5.0

    # Paschal Sundays
    if tempora_id.startswith("Pasc") and is_sunday:
        return 5.0

    # Septuagesima ferias (ordinary ferias, not privileged)
    if tempora_id.startswith("Quadp") and not is_sunday:
        return 1.0

    # Lent ferias (privileged — cannot be displaced by low-rank feasts)
    if tempora_id.startswith("Quad") and not is_sunday:
        return 2.1

    # Advent ferias
    if tempora_id.startswith("Adv") and not is_sunday:
        return 1.15  # Major ferias

    # Ordinary ferias
    return 1.0


# ---------------------------------------------------------------------------
# Sanctoral: date -> Sancti file reference
# ---------------------------------------------------------------------------


def _get_sanctoral_date(dt: datetime.date) -> str:
    """Convert a date to the Sancti MM-DD key.

    Handles leap year February adjustment (Perl get_sday logic):
    Feb 24 in leap years maps to 02-29, Feb 25->24, 26->25, 27->26, 28->27.
    """
    month = dt.month
    day = dt.day

    if calendar.isleap(dt.year) and month == 2:
        if day == 24:
            return "02-29"
        elif day >= 25:
            day -= 1

    return f"{month:02d}-{day:02d}"


# ---------------------------------------------------------------------------
# MassDay result type
# ---------------------------------------------------------------------------


@dataclass
class MassDay:
    """Complete information for the Mass of a given day.

    Contains the occurrence resolution result and, optionally,
    the fully resolved Document AST ready for presentation.
    """

    date: datetime.date
    """The calendar date."""

    tempora_id: Optional[str]
    """The base temporal ID (before remapping), or None."""

    tempora_file: Optional[str]
    """The (remapped) temporal file reference, or None."""

    sanctoral_date: str
    """The MM-DD key for the sanctoral calendar."""

    occurrence: OccurrenceResult
    """The occurrence resolution result."""

    resolved_document: Optional[Document] = None
    """The fully resolved Document AST, if loading succeeded."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_mass_day(
    dt: datetime.date,
    config: MissalConfig,
    tabulae_path: str | Path,
    missa_path: str | Path,
) -> MassDay:
    """Determine the Mass propers for a given date and missal configuration.

    This is the main entry point. It:
    1. Computes the temporal ID for the date.
    2. Remaps it via the Tempora table for the chosen rubric edition.
    3. Looks up the sanctoral calendar.
    4. Applies year-dependent transfers.
    5. Resolves occurrence (who wins, who is commemorated).
    6. Parses and resolves the winning office's document.

    Args:
        dt: The calendar date.
        config: Missal configuration (rubric, mass type, language, etc.).
        tabulae_path: Path to the ``Tabulae/`` directory.
        missa_path: Path to ``missa/Latin/`` (or the language-specific dir).

    Returns:
        A ``MassDay`` with all information about the day's Mass.
    """
    tabulae = Path(tabulae_path)
    missa = Path(missa_path)

    # Load configuration tables
    version_key = _get_version_key(config)
    data_configs = load_data_config(tabulae)

    # Temporal cycle
    year_easter = easter(dt.year, EASTER_WESTERN)
    tempora_id = _get_tempora_id(dt, year_easter)

    # Remap via Tempora table
    tempora_table = load_tempora_merged(tabulae, data_configs, version_key)
    tempora_file: Optional[str] = None
    if tempora_id:
        key = f"Tempora/{tempora_id}"
        remapped = tempora_table.get(key)
        if remapped == "XXXXX":
            tempora_file = None  # Suppressed
        elif remapped:
            tempora_file = remapped
        else:
            tempora_file = key

    tempora_rank = _get_tempora_rank(tempora_id)

    # Sanctoral calendar
    sday = _get_sanctoral_date(dt)
    kalendar = load_kalendar_merged(tabulae, data_configs, version_key)
    sanctoral = kalendar.get(sday)

    # Transfers (with version filtering)
    transfer_stem = (
        data_configs[version_key].transfer_stem
        if version_key in data_configs
        else "1960"
    )
    version_stems = _collect_version_stems(data_configs, version_key)
    transfers = load_transfer(tabulae, transfer_stem, dt.year, version_stems)
    transfer = transfers.get(sday)

    # Occurrence resolution
    occ = resolve_occurrence(
        tempora_id=tempora_id,
        tempora_file=tempora_file,
        tempora_rank=tempora_rank,
        sanctoral=sanctoral,
        transfer=transfer,
        version_key=config.version_string,
        day_of_week=dt.isoweekday(),
    )

    # Build enriched config with temporal info for the resolver
    enriched_config = MissalConfig(
        rubric=config.rubric,
        mass_type=config.mass_type,
        order=config.order,
        language=config.language,
        day_of_week=(dt.isoweekday() % 7) + 1,  # 1=Sunday
        tempus_id=_tempora_id_to_tempus(tempora_id),
        dayname=tempora_id or sday,
        commune="",
        votive=config.votive,
    )

    # Load and resolve the winning document
    resolved_doc: Optional[Document] = None
    if occ.winner_file:
        winner_path = missa / f"{occ.winner_file}.txt"
        if winner_path.is_file():
            try:
                doc = parse_file(str(winner_path))
                resolved_doc = resolve(doc, enriched_config, str(missa))
            except Exception:
                pass

    return MassDay(
        date=dt,
        tempora_id=tempora_id,
        tempora_file=tempora_file,
        sanctoral_date=sday,
        occurrence=occ,
        resolved_document=resolved_doc,
    )


def _tempora_id_to_tempus(tempora_id: Optional[str]) -> str:
    """Convert a Tempora ID to a tempus_id string for the resolver's vero().

    Maps the ID prefix to the liturgical period names used in
    ``(tempore ...)`` conditions.
    """
    if not tempora_id:
        return ""

    if tempora_id.startswith("Adv"):
        return "Adventus"
    if tempora_id.startswith("Nat"):
        return "Nativitatis"
    if tempora_id.startswith("Epi"):
        return "post Epiphaniam"
    if tempora_id.startswith("Quadp"):
        return "Septuagesimæ"
    if tempora_id.startswith("Quad"):
        week = tempora_id[4] if len(tempora_id) > 4 else "1"
        if week in ("5", "6"):
            return "Passionis"
        return "Quadragesimæ"
    if tempora_id.startswith("Pasc0"):
        return "Octava Paschæ"
    if tempora_id.startswith("Pasc"):
        return "post Octavam Paschæ"
    if tempora_id.startswith("Pent"):
        return "post Pentecosten"

    return ""


__all__ = [
    "MassDay",
    "OccurrenceResult",
    "get_mass_day",
]
