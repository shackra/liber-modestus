"""Loader for the Tabulae data files (Kalendaria, Tempora, Transfer).

The Divinum Officium project stores its calendar configuration in text
files under ``web/www/Tabulae/``.  Each rubrical edition has entries in:

- ``data.txt``: maps version names to file stems and inheritance chains.
- ``Kalendaria/<stem>.txt``: saints calendar per edition (only deltas
  from the base version).
- ``Tempora/<stem>.txt``: temporal file remapping per edition.
- ``Transfer/<stem>.txt``: year-dependent feast transfers (by Easter
  date and dominical letter).

This module loads these files and resolves the inheritance chains so
that a query for a given version returns the fully merged result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class KalendarEntry:
    """A single entry in the sanctoral calendar for a given date.

    Parsed from lines like:
    ``01-14=01-14~01-14cc=S. Hilarii=3=S. Felicis=1=``
    """

    date: str
    """Calendar date in MM-DD format."""

    file_ref: str
    """Primary file reference (e.g., '01-14', '01-14cc')."""

    feast_name: str = ""
    """Display name of the feast."""

    rank: float = 0.0
    """Numerical rank value for precedence."""

    commemorations: list[KalendarEntry] = field(default_factory=list)
    """Additional commemorations on the same date (from ``~`` separator)."""

    suppressed: bool = False
    """True if this entry is ``XXXXX`` (removed from the calendar)."""


@dataclass
class VersionConfig:
    """Configuration for a single rubrical version, parsed from data.txt."""

    name: str
    kalendar_stem: str
    transfer_stem: str
    stransfer_stem: str
    base: Optional[str] = None
    transfer_base: Optional[str] = None


# ---------------------------------------------------------------------------
# data.txt parser
# ---------------------------------------------------------------------------


def load_data_config(tabulae_path: Path) -> dict[str, VersionConfig]:
    """Parse ``data.txt`` into a mapping of version name -> VersionConfig.

    Handles the CSV format with optional base/transfer-base columns and
    comment lines starting with ``#``.
    """
    data_file = tabulae_path / "data.txt"
    if not data_file.is_file():
        return {}

    configs: dict[str, VersionConfig] = {}
    lines = data_file.read_text(encoding="utf-8").splitlines()

    for line in lines[1:]:  # skip header
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue

        name = parts[0]
        kal = parts[1]
        transfer = parts[2]
        stransfer = parts[3]
        base = parts[4] if len(parts) > 4 and parts[4] else None
        tbase = parts[5] if len(parts) > 5 and parts[5] else None

        configs[name] = VersionConfig(
            name=name,
            kalendar_stem=kal,
            transfer_stem=transfer,
            stransfer_stem=stransfer,
            base=base,
            transfer_base=tbase,
        )

    return configs


# ---------------------------------------------------------------------------
# Kalendar loader
# ---------------------------------------------------------------------------


def _parse_kalendar_entry(date: str, value: str) -> KalendarEntry:
    """Parse a single kalendar value string into a KalendarEntry.

    Value format: ``fileref=FeastName=rank[=FeastName2=rank2=...]``
    With ``~`` separator for multiple entries on the same date.
    """
    if value == "XXXXX" or value.startswith("XXXXX"):
        return KalendarEntry(date=date, file_ref="XXXXX", suppressed=True)

    # Split on ~ for primary + commemorations
    parts = value.split("~")
    primary = _parse_single_entry(date, parts[0])

    for extra in parts[1:]:
        comm = _parse_single_entry(date, extra)
        primary.commemorations.append(comm)

    return primary


def _parse_single_entry(date: str, raw: str) -> KalendarEntry:
    """Parse one entry (no ~ separator)."""
    raw = raw.strip()
    if raw == "XXXXX":
        return KalendarEntry(date=date, file_ref="XXXXX", suppressed=True)

    fields = raw.split("=")
    file_ref = fields[0] if fields else date
    feast_name = fields[1] if len(fields) > 1 else ""
    rank_str = fields[2] if len(fields) > 2 else "0"

    try:
        rank = float(rank_str) if rank_str else 0.0
    except ValueError:
        rank = 0.0

    return KalendarEntry(
        date=date,
        file_ref=file_ref,
        feast_name=feast_name,
        rank=rank,
    )


def load_kalendar(tabulae_path: Path, stem: str) -> dict[str, KalendarEntry]:
    """Load a single Kalendar file into a date -> entry mapping."""
    kal_file = tabulae_path / "Kalendaria" / f"{stem}.txt"
    if not kal_file.is_file():
        return {}

    entries: dict[str, KalendarEntry] = {}

    for line in kal_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("*"):
            continue

        if "=" not in line:
            continue

        date, _, value = line.partition("=")
        date = date.strip()
        value = value.strip()

        if not date or not value:
            continue

        entries[date] = _parse_kalendar_entry(date, value)

    return entries


def load_kalendar_merged(
    tabulae_path: Path,
    configs: dict[str, VersionConfig],
    version_name: str,
) -> dict[str, KalendarEntry]:
    """Load the fully merged Kalendar for a version (with inheritance).

    Walks the inheritance chain from base to derived, layering entries.
    Derived entries override base entries for the same date.
    """
    config = configs.get(version_name)
    if config is None:
        return {}

    # Build the inheritance chain (base first, derived last)
    chain: list[str] = []
    current: Optional[str] = version_name
    visited: set[str] = set()
    while current and current not in visited:
        visited.add(current)
        chain.append(current)
        cfg = configs.get(current)
        current = cfg.base if cfg else None
    chain.reverse()  # base first

    # Layer entries
    merged: dict[str, KalendarEntry] = {}
    for vname in chain:
        cfg = configs.get(vname)
        if cfg:
            layer = load_kalendar(tabulae_path, cfg.kalendar_stem)
            merged.update(layer)

    return merged


# ---------------------------------------------------------------------------
# Tempora table loader
# ---------------------------------------------------------------------------


def load_tempora_table(tabulae_path: Path, stem: str) -> dict[str, str]:
    """Load a Tempora remapping table.

    Returns a mapping from temporal key (e.g., ``Tempora/Quad6-0``)
    to replacement file (e.g., ``Tempora/Quad6-0r``).

    A value of ``XXXXX`` means the temporal day is suppressed.
    """
    tem_file = tabulae_path / "Tempora" / f"{stem}.txt"
    if not tem_file.is_file():
        return {}

    table: dict[str, str] = {}

    for line in tem_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Format: Key=Value[;;versionFilter]
        # We strip the ;; filter for now (it's for multi-version files)
        if ";;" in line:
            line = line.split(";;")[0].strip()

        if "=" not in line:
            continue

        key, _, val = line.partition("=")
        table[key.strip()] = val.strip()

    return table


def load_tempora_merged(
    tabulae_path: Path,
    configs: dict[str, VersionConfig],
    version_name: str,
) -> dict[str, str]:
    """Load the Tempora table for a version.

    Unlike Kalendar, Tempora tables are NOT inherited.  Each version's
    Tempora table lists substitutions relative to the base filesystem,
    NOT relative to the parent version's table.  So we load ONLY the
    version's own table.  If the version has no Tempora file, we try
    its base (the Perl code does fall through the base chain for this).
    """
    config = configs.get(version_name)
    if config is None:
        return {}

    # Try the version's own Tempora file first, then walk the base chain
    current: Optional[str] = version_name
    visited: set[str] = set()
    while current and current not in visited:
        visited.add(current)
        cfg = configs.get(current)
        if cfg:
            table = load_tempora_table(tabulae_path, cfg.kalendar_stem)
            if table:
                return table
        current = cfg.base if cfg else None

    return {}


# ---------------------------------------------------------------------------
# Transfer loader
# ---------------------------------------------------------------------------


def _compute_easter_key(year: int) -> str:
    """Compute the Easter date key for Transfer file lookup.

    Returns a string like ``413`` for April 13, ``322`` for March 22.
    """
    from dateutil.easter import EASTER_WESTERN, easter

    e = easter(year, EASTER_WESTERN)
    return f"{e.month}{e.day:02d}"


def _compute_dominical_letter(year: int) -> str:
    """Compute the dominical letter for Transfer file lookup.

    Returns a lowercase letter 'a' through 'g'.

    Replicates the Perl formula from Directorium.pm::

        my $letter = ($easter - 319 + ($easter[1] == 4 ? 1 : 0)) % 7;

    where ``$easter = month * 100 + day`` of Easter Sunday.
    """
    from dateutil.easter import EASTER_WESTERN, easter

    e = easter(year, EASTER_WESTERN)
    easter_encoded = e.month * 100 + e.day
    idx = (easter_encoded - 319 + (1 if e.month == 4 else 0)) % 7
    letters = ("a", "b", "c", "d", "e", "f", "g")
    return letters[idx]


def _collect_version_stems(
    configs: dict[str, VersionConfig], version_name: str
) -> set[str]:
    """Collect all identifier stems in the inheritance chain for a version.

    The Transfer file filters reference these stems (e.g., ``1570``,
    ``DA``, ``1960``, ``M1930``).  Both the ``kalendar_stem`` and the
    ``transfer_stem`` are collected, because some versions use different
    identifiers in Transfer filters vs Kalendar filenames (e.g., Divino
    Afflatu uses ``1939`` as kalendar stem but ``DA`` as transfer stem).
    """
    stems: set[str] = set()
    current: Optional[str] = version_name
    visited: set[str] = set()
    while current and current not in visited:
        visited.add(current)
        cfg = configs.get(current)
        if cfg:
            stems.add(cfg.kalendar_stem)
            stems.add(cfg.transfer_stem)
        current = cfg.base if cfg else None
    return stems


def load_transfer(
    tabulae_path: Path,
    stem: str,
    year: int,
    allowed_stems: set[str] | None = None,
) -> dict[str, str]:
    """Load year-dependent feast transfers, filtered by version.

    Merges the dominical letter file and Easter-date file for the given
    year.  Only entries whose ``;;version_filter`` contains a stem from
    ``allowed_stems`` (or entries without any filter) are included.

    Args:
        tabulae_path: Path to the Tabulae directory.
        stem: The transfer stem from data.txt (used for Easter-date files).
        year: The calendar year.
        allowed_stems: Set of Kalendar stems that this version inherits
            (e.g., ``{'1960', '1955', '1954', '1939', '1906', '1888', '1570'}``).

    Returns:
        A mapping from calendar date (MM-DD) to the transferred
        office file reference.
    """
    transfers: dict[str, str] = {}

    # Load dominical letter file
    letter = _compute_dominical_letter(year)
    letter_file = tabulae_path / "Transfer" / f"{letter}.txt"
    if letter_file.is_file():
        transfers.update(_parse_transfer_file(letter_file, allowed_stems))

    # Load Easter-date file
    easter_key = _compute_easter_key(year)
    easter_file = tabulae_path / "Transfer" / f"{easter_key}.txt"
    if easter_file.is_file():
        transfers.update(_parse_transfer_file(easter_file, allowed_stems))

    return transfers


def _parse_transfer_file(
    path: Path, allowed_stems: set[str] | None = None
) -> dict[str, str]:
    """Parse a single Transfer file, filtering by version stems.

    Each line has the format ``date=value[;;stem1 stem2 ...]``.
    If ``allowed_stems`` is provided, only entries whose version filter
    contains at least one of the allowed stems are included.  Entries
    without a ``;;`` filter are always included.

    When multiple lines share the same date key, the last matching one
    wins (later lines override earlier ones).
    """
    result: dict[str, str] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, _, val = line.partition("=")
        key = key.strip()

        # Only calendar dates (MM-DD format) or special keys we recognize
        if not (len(key) == 5 and key[2] == "-"):
            continue

        # Parse version filter
        if ";;" in val:
            val_part, _, filter_part = val.partition(";;")
            val_part = val_part.strip()
            filter_part = filter_part.strip()

            if allowed_stems and filter_part:
                filter_stems = set(filter_part.split())
                if not filter_stems.intersection(allowed_stems):
                    continue  # This entry is not for our version

            result[key] = val_part
        else:
            # No filter — always include
            result[key] = val.strip()

    return result
