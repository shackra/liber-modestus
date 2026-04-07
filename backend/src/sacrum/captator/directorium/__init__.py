"""Directorium: liturgical calendar engine for the traditional Roman Missa.

Given a date and a ``MissalConfig``, determines which Mass propers to
use by resolving the temporal cycle, sanctoral calendar, transfers,
and occurrence precedence rules.

Usage::

    from datetime import date
    from sacrum.captator.resolver import MissalConfig, Rubric
    from sacrum.captator.directorium import get_mass_propers, MassDay

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
import re as _re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dateutil.easter import EASTER_WESTERN, easter

from sacrum.captator.parser import Document, parse_file
from sacrum.captator.resolver import MissalConfig, Rubric, resolve
from sacrum.captator.resolver.config import OrderVariant
from sacrum.captator.resolver.evaluator import vero

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
# Display name resolution (YAML database + fast file fallback)
# ---------------------------------------------------------------------------

_FEAST_NAMES_PATH = Path(__file__).parent.parent.parent.parent / "feast_names.yaml"


@lru_cache(maxsize=1)
def _load_feast_names_db() -> dict[str, dict[str, str]]:
    """Load the feast names YAML database (cached).

    Returns a mapping of ``latin_name -> {language: translated_name}``.
    Only entries with a non-empty translation are included.
    """
    if not _FEAST_NAMES_PATH.is_file():
        return {}
    try:
        import yaml

        raw = yaml.safe_load(_FEAST_NAMES_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        # Filter out empty translations
        db: dict[str, dict[str, str]] = {}
        for latin_name, translations in raw.items():
            if isinstance(translations, dict):
                filtered = {
                    lang: name
                    for lang, name in translations.items()
                    if name  # skip None / empty
                }
                if filtered:
                    db[latin_name] = filtered
        return db
    except Exception:
        return {}


def _extract_rank_display_name(filepath: Path) -> str:
    """Extract the feast display name from a file's ``[Rank]`` section.

    This is a fast, targeted read that only scans the first lines of the
    file until it finds ``[Rank]`` and the ``;;``-delimited rank line.
    It does NOT parse the entire file (~0.02 ms vs ~0.9 ms for a full
    parse).

    Returns an empty string if the file does not exist or has no
    ``[Rank]`` section.
    """
    if not filepath.is_file():
        return ""
    try:
        in_rank = False
        with filepath.open(encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip()
                if stripped == "[Rank]":
                    in_rank = True
                    continue
                if in_rank and stripped:
                    if ";;" in stripped:
                        return stripped.split(";;")[0].strip()
                    if stripped.startswith("["):
                        break
    except OSError:
        pass
    return ""


def _extract_officium_name(filepath: Path) -> str:
    """Extract the office name from a file's ``[Officium]`` section.

    Temporal files (``Tempora/*.txt``) store the display name in the
    ``[Officium]`` section rather than in ``[Rank]``.  This function
    provides a fast fallback for those cases.

    Returns an empty string if the file does not exist or has no
    ``[Officium]`` section.
    """
    if not filepath.is_file():
        return ""
    try:
        in_officium = False
        with filepath.open(encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip()
                if stripped == "[Officium]":
                    in_officium = True
                    continue
                if in_officium and stripped:
                    if stripped.startswith("["):
                        break
                    return stripped
    except OSError:
        pass
    return ""


def _get_display_name(
    winner_file: str, winner_name: str, language: str, missa: Path
) -> str:
    """Get the feast display name in the requested language.

    Lookup order:
    1. The ``feast_names.yaml`` database (fastest, user-curated).
    2. The translated file's ``[Rank]`` section (fast file scan).
    3. The translated file's ``[Officium]`` section (for Tempora files).
    4. The Latin file's ``[Rank]`` section.
    5. The Latin file's ``[Officium]`` section.
    6. The ``winner_name`` from the Kalendar (always Latin).
    """
    if not winner_file:
        return winner_name

    # Determine the Latin canonical name first (needed for YAML lookup)
    latin_path = missa / f"{winner_file}.txt"
    latin_name = (
        _extract_rank_display_name(latin_path)
        or _extract_officium_name(latin_path)
        or winner_name
    )

    # 1. Try the YAML database
    if language and language != "Latin":
        db = _load_feast_names_db()
        # Try both the Latin [Rank] name and the Kalendar name
        for key in (latin_name, winner_name):
            if key in db and language in db[key]:
                return db[key][language]

    # 2. Try the translated file's [Rank] section
    if language and language != "Latin":
        missa_root = missa.parent
        lang_path = missa_root / language / f"{winner_file}.txt"
        name = _extract_rank_display_name(lang_path)
        if name:
            return name
        # 3. Try the translated file's [Officium] section
        name = _extract_officium_name(lang_path)
        if name:
            return name

    # 4. Use the Latin [Rank] name or [Officium] name
    if latin_name:
        return latin_name

    # 5. Fallback to the Kalendar name
    return winner_name


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

    # Resolve the display name in the configured language.
    # The occurrence result has the canonical Latin name from the Kalendar
    # in winner_name.  We copy that to winner_name_canonical and then
    # overwrite winner_name with the translated name.
    canonical = occ.winner_name
    translated = _get_display_name(occ.winner_file, canonical, config.language, missa)
    occ.winner_name_canonical = canonical
    occ.winner_name = translated

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


# ---------------------------------------------------------------------------
# Liturgical colour
# ---------------------------------------------------------------------------


class LiturgicalColor(Enum):
    """The six liturgical vestment colours of the Roman Rite."""

    WHITE = "white"
    """Feasts of Our Lord (except the Cross), Our Lady, Confessors,
    Virgins, Angels, Dedication, and the Easter/Christmas seasons."""

    RED = "red"
    """Pentecost, feasts of Apostles, Evangelists, Martyrs,
    and the Precious Blood / Holy Cross."""

    GREEN = "green"
    """Sundays and ferias after Epiphany and after Pentecost
    (Ordinary Time)."""

    VIOLET = "violet"
    """Advent, Lent, Passiontide, Vigils, Ember Days,
    and Rogation Days."""

    BLACK = "black"
    """Masses for the Dead (Requiem) and Good Friday."""

    ROSE = "rose"
    """Gaudete Sunday (Advent III) and Laetare Sunday (Lent IV)."""


def _get_liturgical_color(
    latin_name: str,
    tempora_id: Optional[str] = None,
) -> LiturgicalColor:
    """Determine the liturgical vestment colour from the Latin feast name.

    This is a faithful port of the Perl ``liturgical_color()`` function
    from ``DivinumOfficium::Main`` (Main.pm, lines 25-39), but mapped
    to the traditional five + rose liturgical colours instead of CSS
    display colours.

    The Perl function uses cascading regex tests on the Latin feast name
    to determine a *display* colour.  The mapping from Perl display
    colours to real vestment colours is:

    ==========  =====================  ==============================
    Perl color  Vestment colour        Meaning
    ==========  =====================  ==============================
    blue        WHITE                  Marian feasts
    red         RED                    Martyrs, Apostles, Pentecost…
    grey        BLACK                  Requiem, Good Friday
    purple      VIOLET                 Penitential seasons / vigils
    black*      WHITE                  Confessors, Easter, Christmas…
    green       GREEN                  Ordinary Time
    ==========  =====================  ==============================

    (*) In the Perl code, 'black' is the default font colour for
    white-vestment feasts (confessors, dedications, Easter, etc.).

    Additionally, two days that traditionally use **rose** vestments
    are detected via ``tempora_id``:
    - Gaudete Sunday (``Adv3-0``)
    - Laetare Sunday (``Quad4-0``)
    """
    # Rose vestments: Gaudete (Advent III) and Laetare (Lent IV)
    if tempora_id in ("Adv3-0", "Quad4-0"):
        return LiturgicalColor.ROSE

    name = latin_name

    # 1. Marian feasts (Perl: blue → WHITE)
    if _re.search(r"(?:Beat|Sanct)(?:ae|æ) Mari", name) and not _re.search(
        r"Vigil", name
    ):
        return LiturgicalColor.WHITE

    # 2. Pentecost Vigil, Pentecost Ember Days, Beheading, Martyrs (Perl: red → RED)
    if _re.search(
        r"(?:Vigilia Pentecostes|Quattuor Temporum Pentecostes|Decollatione|Martyr)",
        name,
        _re.IGNORECASE,
    ):
        return LiturgicalColor.RED

    # 3. Dead / Good Friday / Death (Perl: grey → BLACK)
    if _re.search(r"(?:Defunctorum|Parasceve|Morte)", name, _re.IGNORECASE):
        return LiturgicalColor.BLACK

    # 4. Specific vigils that are WHITE, not violet
    #    (Perl: black → WHITE for Ascension Vigil, Epiphany Vigil)
    if _re.search(r"^In Vigilia Ascensionis|^In Vigilia Epiphaniæ", name):
        return LiturgicalColor.WHITE

    # 5. Penitential seasons (Perl: purple → VIOLET)
    if _re.search(
        r"(?:Vigilia|Quattuor|Rogatio|Passion|Palmis|gesim"
        r"|(?:Majoris )?Hebdomadæ(?: Sanctæ)?|Sabbato Sancto"
        r"|Dolorum|Ciner|Adventus)",
        name,
        _re.IGNORECASE,
    ):
        return LiturgicalColor.VIOLET

    # 6. Confessors, Dedications, Easter, etc. (Perl: black → WHITE)
    if _re.search(
        r"(?:Conversione|Dedicatione|Cathedra|oann|Pasch|Confessor|Ascensio|Cena)",
        name,
        _re.IGNORECASE,
    ):
        return LiturgicalColor.WHITE

    # 7. Ordinary Time (Perl: green → GREEN)
    if _re.search(
        r"(?:Pentecosten(?!.*infra octavam)|Epiphaniam|post octavam)",
        name,
        _re.IGNORECASE,
    ):
        return LiturgicalColor.GREEN

    # 8. Pentecost, Evangelists, Innocents, Blood, Cross, Apostles (Perl: red → RED)
    if _re.search(
        r"(?:Pentecostes|Evangel|Innocentium|Sanguinis|Cruc|Apostol)",
        name,
        _re.IGNORECASE,
    ):
        return LiturgicalColor.RED

    # 9. Default: WHITE (confessors, virgins, angels, etc.)
    # The Perl code returns 'black' (font colour) here, which maps to
    # white vestments for the majority of remaining feasts.
    return LiturgicalColor.WHITE


# ---------------------------------------------------------------------------
# Rank class extraction
# ---------------------------------------------------------------------------


def _extract_rank_class(
    filepath: Path,
    config: MissalConfig,
) -> str:
    """Extract the liturgical rank class from a file's ``[Rank]`` section.

    The ``[Rank]`` section may contain multiple conditional variants::

        [Rank]
        ;;Duplex I classis cum octava communi;;6.5;;ex C1
        (sed rubrica 196)
        ;;Duplex I classis;;6;;ex C1

    This function evaluates the ``(sed ...)`` conditions against the
    given *config* to select the correct variant, then returns the
    rank-class field (the second ``;;``-delimited field, e.g.,
    ``"Duplex I classis"``).

    Returns an empty string if the file does not exist or has no
    parseable ``[Rank]`` section.
    """
    if not filepath.is_file():
        return ""
    try:
        in_rank = False
        current_rank_line: Optional[str] = None
        with filepath.open(encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip()
                if stripped == "[Rank]":
                    in_rank = True
                    continue
                if not in_rank:
                    continue
                # End of section
                if stripped.startswith("["):
                    break

                # Skip empty lines
                if not stripped:
                    continue

                # Conditional line: (sed rubrica ...)
                if stripped.startswith("(") and stripped.endswith(")"):
                    condition = stripped[1:-1].strip()
                    # Remove 'sed' prefix
                    if condition.lower().startswith("sed "):
                        condition = condition[4:].strip()
                    if vero(condition, config):
                        # Next rank line overrides the current one
                        current_rank_line = None
                        continue
                    else:
                        # Condition false: skip the next rank line
                        # Read and discard the next non-empty, non-conditional line
                        for inner_line in f:
                            inner_stripped = inner_line.strip()
                            if inner_stripped.startswith("["):
                                # Reached next section — stop entirely
                                if current_rank_line and ";;" in current_rank_line:
                                    parts = current_rank_line.split(";;")
                                    return parts[1].strip() if len(parts) > 1 else ""
                                return ""
                            if inner_stripped and not inner_stripped.startswith("("):
                                break  # Discarded the line
                        continue

                # Regular rank line
                if ";;" in stripped:
                    current_rank_line = stripped

        if current_rank_line and ";;" in current_rank_line:
            parts = current_rank_line.split(";;")
            return parts[1].strip() if len(parts) > 1 else ""
    except OSError:
        pass
    return ""


# ---------------------------------------------------------------------------
# MassName (existing)
# ---------------------------------------------------------------------------


@dataclass
class MassName:
    """The name of the Mass for a given date.

    Provides both the display name (possibly translated) and the
    canonical Latin name, plus basic metadata for calendar rendering.
    """

    name: str
    """Display name of the Mass in the configured language."""

    name_canonical: str
    """Canonical Latin name (always Latin regardless of language)."""

    rank: float
    """Numerical rank of the winning office (higher = more solemn)."""

    is_sanctoral: bool
    """True if the saint's feast won over the temporal cycle."""

    is_commemoration: bool
    """True if the temporal day has commemorations."""

    commemorations: list[str]
    """Display names of commemorated offices."""


# ---------------------------------------------------------------------------
# Default paths (derived from package location)
# ---------------------------------------------------------------------------

_DO_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "divinum-officium" / "web" / "www"
)


def _default_tabulae_path() -> Path:
    return _DO_ROOT / "Tabulae"


def _default_missa_path(language: str = "Latin") -> Path:
    return _DO_ROOT / "missa" / language


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------


def get_mass_name_for_date(
    dt: datetime.date,
    rubric: Rubric = Rubric.RUBRICAE_1960,
    language: str = "Latin",
) -> MassName:
    """Return the name of the Mass for a given date and rubrical edition.

    This is a convenience function for calendar rendering.  It calls
    ``get_mass_day`` internally but skips the expensive document
    parsing/resolution step -- only the occurrence resolution and
    name lookup are performed.

    Args:
        dt: The calendar date.
        rubric: Rubrical edition (default: ``RUBRICAE_1960``, i.e. the
            1962 Missal).
        language: Language for the feast name (e.g., ``'Latin'``,
            ``'Espanol'``, ``'English'``).  Must match a directory
            name under ``missa/``.

    Returns:
        A ``MassName`` with the display name, canonical Latin name,
        rank, and basic metadata.

    Example::

        >>> from datetime import date
        >>> from sacrum.captator.directorium import get_mass_name_for_date
        >>> m = get_mass_name_for_date(date(2025, 12, 25))
        >>> m.name
        'In Nativitate Domini'

        >>> m = get_mass_name_for_date(date(2025, 12, 25), language="Espanol")
        >>> m.name  # translated if available
        'En la Natividad del Señor'
    """
    config = MissalConfig(rubric=rubric, language=language)
    tabulae = _default_tabulae_path()
    missa = _default_missa_path("Latin")  # Latin is always the base

    day = get_mass_day(dt, config, tabulae, missa)
    occ = day.occurrence

    return MassName(
        name=occ.winner_name,
        name_canonical=occ.winner_name_canonical,
        rank=occ.winner_rank,
        is_sanctoral=occ.is_sanctoral,
        is_commemoration=len(occ.commemorations) > 0,
        commemorations=occ.commemoration_names,
    )


def get_mass_names_for_month(
    year: int,
    month: int,
    rubric: Rubric = Rubric.RUBRICAE_1960,
    language: str = "Latin",
) -> list[MassName]:
    """Return the Mass name for every day of a given month.

    Convenience function for calendar views.  Returns a list of
    ``MassName`` objects, one per day (index 0 = day 1).

    Args:
        year: Calendar year.
        month: Calendar month (1-12).
        rubric: Rubrical edition (default: 1962 Missal).
        language: Language for feast names.

    Returns:
        A list with one ``MassName`` per day of the month.
    """
    _, num_days = calendar.monthrange(year, month)
    return [
        get_mass_name_for_date(datetime.date(year, month, day), rubric, language)
        for day in range(1, num_days + 1)
    ]


def get_mass_names_for_year(
    year: int,
    rubric: Rubric = Rubric.RUBRICAE_1960,
    language: str = "Latin",
) -> list[MassName]:
    """Return the Mass name for every day of a given year.

    Convenience function for full-year calendar generation.

    Args:
        year: Calendar year.
        rubric: Rubrical edition (default: 1962 Missal).
        language: Language for feast names.

    Returns:
        A list with one ``MassName`` per day of the year (Jan 1 first).
    """
    results: list[MassName] = []
    for month in range(1, 13):
        results.extend(get_mass_names_for_month(year, month, rubric, language))
    return results


# ---------------------------------------------------------------------------
# MassInfo: enriched calendar entry
# ---------------------------------------------------------------------------


@dataclass
class MassInfo:
    """Enriched information about the Mass of a given date.

    Designed for calendar (iCal) generation.  Contains everything
    ``MassName`` provides, plus the liturgical vestment colour and
    the textual rank class.
    """

    date: datetime.date
    """The calendar date."""

    name: str
    """Display name of the Mass in the configured language."""

    name_canonical: str
    """Canonical Latin name (always Latin regardless of language)."""

    rank: float
    """Numerical rank of the winning office (higher = more solemn)."""

    rank_name: str
    """Textual rank class (e.g., ``'Duplex I classis'``,
    ``'Semiduplex'``, ``'Feria'``).  Extracted from the ``[Rank]``
    section of the winning file."""

    color: LiturgicalColor
    """Liturgical vestment colour for the day."""

    is_sanctoral: bool
    """True if the saint's feast won over the temporal cycle."""

    commemorations: list[str]
    """Display names of commemorated offices."""


def get_mass_info_for_date(
    dt: datetime.date,
    rubric: Rubric = Rubric.RUBRICAE_1960,
    language: str = "Latin",
) -> MassInfo:
    """Return enriched Mass information for a given date.

    This is the recommended entry point for building liturgical
    calendars (e.g., iCal generation).  It performs occurrence
    resolution, name translation, rank-class extraction, and
    liturgical-colour determination — all without parsing the full
    document AST.

    Args:
        dt: The calendar date.
        rubric: Rubrical edition (default: ``RUBRICAE_1960``, i.e. the
            1962 Missal).
        language: Language for the feast name (e.g., ``'Latin'``,
            ``'Espanol'``, ``'English'``).  Must match a directory
            name under ``missa/``.

    Returns:
        A ``MassInfo`` with the display name, canonical Latin name,
        rank, rank class, liturgical colour, and commemorations.

    Example::

        >>> from datetime import date
        >>> from sacrum.captator.directorium import get_mass_info_for_date
        >>> info = get_mass_info_for_date(date(2025, 12, 25), language="Espanol")
        >>> info.name
        'En la Natividad del Señor'
        >>> info.color
        <LiturgicalColor.WHITE: 'white'>
        >>> info.rank_name
        'Duplex I Classis'
    """
    config = MissalConfig(rubric=rubric, language=language)
    tabulae = _default_tabulae_path()
    missa = _default_missa_path("Latin")  # Latin is always the base

    day = get_mass_day(dt, config, tabulae, missa)
    occ = day.occurrence

    # Resolve the real Latin name for the winning file.
    # occ.winner_name_canonical may be a bare file-ref (e.g., "Adv1-0")
    # for temporal offices.  We need the real Latin feast name from the
    # file's [Rank] or [Officium] section for accurate colour detection.
    canonical_latin = occ.winner_name_canonical
    rank_name = ""
    if occ.winner_file:
        winner_path = missa / f"{occ.winner_file}.txt"
        real_latin = _extract_rank_display_name(winner_path) or _extract_officium_name(
            winner_path
        )
        if real_latin:
            canonical_latin = real_latin
        rank_name = _extract_rank_class(winner_path, config)

    # Liturgical colour from the resolved Latin name
    color = _get_liturgical_color(canonical_latin, day.tempora_id)

    return MassInfo(
        date=dt,
        name=occ.winner_name,
        name_canonical=canonical_latin,
        rank=occ.winner_rank,
        rank_name=rank_name,
        color=color,
        is_sanctoral=occ.is_sanctoral,
        commemorations=occ.commemoration_names,
    )


def get_mass_info_for_month(
    year: int,
    month: int,
    rubric: Rubric = Rubric.RUBRICAE_1960,
    language: str = "Latin",
) -> list[MassInfo]:
    """Return enriched Mass information for every day of a given month.

    Convenience function for calendar generation.

    Args:
        year: Calendar year.
        month: Calendar month (1-12).
        rubric: Rubrical edition (default: 1962 Missal).
        language: Language for feast names.

    Returns:
        A list with one ``MassInfo`` per day of the month (index 0 = day 1).
    """
    _, num_days = calendar.monthrange(year, month)
    return [
        get_mass_info_for_date(datetime.date(year, month, day), rubric, language)
        for day in range(1, num_days + 1)
    ]


def get_mass_info_for_year(
    year: int,
    rubric: Rubric = Rubric.RUBRICAE_1960,
    language: str = "Latin",
) -> list[MassInfo]:
    """Return enriched Mass information for every day of a given year.

    Convenience function for full-year calendar generation.

    Args:
        year: Calendar year.
        rubric: Rubrical edition (default: 1962 Missal).
        language: Language for feast names.

    Returns:
        A list with one ``MassInfo`` per day of the year (Jan 1 first).
    """
    results: list[MassInfo] = []
    for month in range(1, 13):
        results.extend(get_mass_info_for_month(year, month, rubric, language))
    return results


__all__ = [
    "LiturgicalColor",
    "MassDay",
    "MassInfo",
    "MassName",
    "OccurrenceResult",
    "get_mass_day",
    "get_mass_info_for_date",
    "get_mass_info_for_month",
    "get_mass_info_for_year",
    "get_mass_name_for_date",
    "get_mass_names_for_month",
    "get_mass_names_for_year",
]
