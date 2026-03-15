"""Occurrence resolution for Missa: determines which office wins when
temporal and sanctoral feasts coincide.

This is a simplified version of the Perl ``occurrence()`` function
from ``horascommon.pl``, focused exclusively on Missa (no Vespers
concurrence, no hours-specific logic).

The core rule: the office with the higher numerical rank wins.
The loser becomes a commemoration (its Collect, Secret, and
Postcommunion are appended to the winner's Mass).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .tables import KalendarEntry


@dataclass
class OccurrenceResult:
    """Result of occurrence resolution for a given date.

    Provides the winning office (whose Mass proper is celebrated)
    and any commemorations (whose collects/secrets/postcommunions
    are appended).
    """

    winner_file: str
    """File reference for the winning office (e.g., 'Tempora/Adv1-0',
    'Sancti/01-06', 'Sancti/03-19')."""

    winner_rank: float
    """Numerical rank of the winning office."""

    winner_name: str = ""
    """Display name of the winning feast."""

    is_sanctoral: bool = False
    """True if the sanctoral office won over the temporal."""

    is_bmv_saturday: bool = False
    """True if the Mass of the BVM is automatically assigned (Saturday)."""

    is_requiem: bool = False
    """True if this is a Requiem / Defunctorum Mass (e.g., Nov 2)."""

    commemorations: list[str] = field(default_factory=list)
    """File references for commemorated offices (loser + any extras)."""

    commemoration_names: list[str] = field(default_factory=list)
    """Display names of commemorated offices."""


def _estimate_transfer_rank(file_ref: str) -> float:
    """Estimate the rank of a transferred feast from its file reference.

    Well-known high-rank transfers get their correct rank.  Unknown
    transfers default to 5.0 (Duplex II classis), which is the most
    common case for transferred feasts.
    """
    ref = file_ref.lower()

    # Duplex I classis (rank 6+) transfers
    if "10-du" in ref:
        return 6.0  # Christ the King
    if "tempora/nat" in ref and "-0" in ref:
        return 5.0  # Sunday within Christmas Octave
    if ref.startswith("tempora/"):
        return 5.0  # Temporal transfers usually Sunday-level

    # Default for sanctoral transfers
    return 5.0


def _is_defunctorum(feast_name: str) -> bool:
    """Check if a feast name indicates a Defunctorum / Requiem Mass."""
    lower = feast_name.lower()
    return "defunctorum" in lower or "fidelium defunctorum" in lower


def _determine_c10_variant(tempora_id: Optional[str]) -> str:
    """Choose the BVM Saturday commune variant based on the liturgical season.

    Returns a Commune file ref like 'C10', 'C10a' (Advent), etc.
    """
    if tempora_id is None:
        return "C10"
    if tempora_id.startswith("Adv"):
        return "C10a"
    if tempora_id.startswith("Nat") or tempora_id.startswith("Epi1-"):
        return "C10b"  # Nativity to Purification (Jan-Feb 1)
    if tempora_id.startswith("Epi") or tempora_id.startswith("Quad"):
        return "C10c"  # Epiphany / Lent
    if tempora_id.startswith("Pasc"):
        return "C10Pasc"  # Paschaltide
    return "C10"  # Default (Trinity to Advent)


def resolve_occurrence(
    tempora_id: Optional[str],
    tempora_file: Optional[str],
    tempora_rank: float,
    sanctoral: Optional[KalendarEntry],
    transfer: Optional[str],
    version_key: str,
    day_of_week: int = 0,
) -> OccurrenceResult:
    """Resolve which office wins between temporal and sanctoral.

    Args:
        tempora_id: The base temporal ID (e.g., 'Adv1-0', 'Pent03-2').
        tempora_file: The (possibly remapped) temporal file reference
            (e.g., 'Tempora/Adv1-0o' for Tridentine).
        tempora_rank: Numerical rank of the temporal office.
        sanctoral: The sanctoral KalendarEntry for the date, or None.
        transfer: A transferred office file reference, or None.
        version_key: Version identifier for rubric-dependent adjustments
            (e.g., 'Rubrics 1960', 'Trident 1570').
        day_of_week: ISO weekday (1=Monday, ..., 7=Sunday). Used for
            BVM Saturday detection (6=Saturday).

    Returns:
        An ``OccurrenceResult`` indicating the winner and commemorations.
    """
    # Handle transferred feasts: they replace the normal sanctoral.
    # The transfer value can contain ~-separated commemorations.
    if transfer:
        parts = transfer.split("~")
        primary_ref = parts[0].strip()

        # Try to determine the rank from the file reference pattern.
        # Some transfers are well-known high-rank feasts:
        transfer_rank = _estimate_transfer_rank(primary_ref)

        sanctoral = KalendarEntry(
            date=sanctoral.date if sanctoral else "",
            file_ref=primary_ref,
            feast_name="(transferred)",
            rank=transfer_rank,
        )
        # Add transfer commemorations
        for extra in parts[1:]:
            extra = extra.strip()
            if extra and extra != "XXXXX" and extra != "X-X":
                sanctoral.commemorations.append(
                    KalendarEntry(date=sanctoral.date, file_ref=extra, rank=1.0)
                )

    # --- No temporal office (e.g., Christmastide dates without Tempora files) ---
    if not tempora_file:
        if sanctoral and not sanctoral.suppressed:
            comms: list[str] = []
            comm_names: list[str] = []
            for c in sanctoral.commemorations:
                if not c.suppressed and c.file_ref != "XXXXX":
                    comms.append(f"Sancti/{c.file_ref}")
                    comm_names.append(c.feast_name)
            return OccurrenceResult(
                winner_file=f"Sancti/{sanctoral.file_ref}",
                winner_rank=sanctoral.rank,
                winner_name=sanctoral.feast_name,
                is_sanctoral=True,
                is_requiem=_is_defunctorum(sanctoral.feast_name),
                commemorations=comms,
                commemoration_names=comm_names,
            )
        return OccurrenceResult(winner_file="", winner_rank=0)

    # --- BVM Saturday (Missa S. Mariae in Sabbato) ---
    # Automatically assigned when it's Saturday, both temporal and
    # sanctoral ranks are below 1.4, and there's no transferred vigil.
    s_rank_for_bmv = sanctoral.rank if (sanctoral and not sanctoral.suppressed) else 0.0
    if (
        day_of_week == 6
        and tempora_rank < 1.4
        and s_rank_for_bmv < 1.4
        and not transfer
    ):
        c10 = _determine_c10_variant(tempora_id)
        return OccurrenceResult(
            winner_file=f"Commune/{c10}",
            winner_rank=1.3,
            winner_name="Sanctæ Mariæ in Sabbato",
            is_sanctoral=False,
            is_bmv_saturday=True,
        )

    # --- No sanctoral office ---
    if not sanctoral or sanctoral.suppressed:
        return OccurrenceResult(
            winner_file=tempora_file,
            winner_rank=tempora_rank,
            winner_name=tempora_id or "",
            is_sanctoral=False,
        )

    # --- Both temporal and sanctoral exist: compare ranks ---
    s_rank = sanctoral.rank
    t_rank = tempora_rank

    # Rank adjustments based on version
    # Pre-Divino Afflatu: minor Sundays (rank 5) are beaten by any Duplex (3+)
    # This is one of the most important rubric differences.
    is_1960 = "196" in version_key or "1955" in version_key
    is_tridentine = "Trident" in version_key
    is_divino = "Divino" in version_key or "1939" in version_key

    # Sunday detection
    is_sunday = tempora_id is not None and tempora_id.endswith("-0")

    if is_sunday and t_rank < 6:
        # Advent and Lent Sundays are NEVER outranked (rank >= 5 in all editions)
        is_major_sunday = tempora_id is not None and (
            tempora_id.startswith("Adv")
            or tempora_id.startswith("Quad")
            or tempora_id.startswith("Quadp")
            or tempora_id.startswith("Pasc")
        )
        if not is_major_sunday:
            # Minor Sunday rank adjustments by edition
            # (only ordinary Sundays after Epiphany / Pentecost)
            if is_tridentine and not is_divino:
                # Pre-Divino: minor Sundays rank 2.9 (beaten by Duplex 3+)
                t_rank = 2.9
            elif is_divino and not is_1960:
                # Divino Afflatu: minor Sundays rank 4.9 (beat Duplex but
                # not Duplex majus)
                t_rank = 4.9
            # 1960: minor Sundays keep their rank (usually 5 = II classis)

    # Privileged ferias (Advent after Dec 16, Lent, Ember Days)
    # These have rank 1.1-2.1 but cannot be displaced by low-rank feasts
    is_privileged_feria = (
        tempora_id is not None
        and not is_sunday
        and t_rank >= 1.1
        and (
            (tempora_id.startswith("Adv") and t_rank >= 1.15)
            or tempora_id.startswith("Quad")
        )
    )

    # Comparison
    if t_rank >= 7:
        # Highest rank temporal (Easter, Christmas, Triduum) always wins
        winner_is_temporal = True
    elif s_rank >= 7:
        # Highest rank sanctoral always wins
        winner_is_temporal = False
    elif s_rank > t_rank:
        # Higher rank wins
        winner_is_temporal = False
    elif t_rank > s_rank:
        winner_is_temporal = True
    elif s_rank == t_rank:
        # Tie: temporal wins on Sundays and privileged ferias,
        # sanctoral wins otherwise
        winner_is_temporal = is_sunday or is_privileged_feria
    else:
        winner_is_temporal = True

    # Special case: 1955+ Semiduplex reduction
    # Feasts that were Semiduplex (2.x) are reduced to Simplex (1.2)
    # and can only be commemorated, not celebrated
    if is_1960 and s_rank >= 2.0 and s_rank < 3.0:
        # Semiduplex feasts become commemorations in 1960
        s_rank = 1.2
        winner_is_temporal = True

    # Build result
    comms = []
    comm_names = []

    if winner_is_temporal:
        # Temporal wins; sanctoral is commemorated (if rank allows)
        if sanctoral.rank >= 1.0 and not sanctoral.suppressed:
            comms.append(f"Sancti/{sanctoral.file_ref}")
            comm_names.append(sanctoral.feast_name)
        # Add any additional commemorations from the kalendar entry
        for c in sanctoral.commemorations:
            if not c.suppressed and c.file_ref != "XXXXX":
                comms.append(f"Sancti/{c.file_ref}")
                comm_names.append(c.feast_name)

        return OccurrenceResult(
            winner_file=tempora_file,
            winner_rank=tempora_rank,
            winner_name=tempora_id or "",
            is_sanctoral=False,
            commemorations=comms,
            commemoration_names=comm_names,
        )
    else:
        # Sanctoral wins; temporal is commemorated (on Sundays and
        # privileged ferias only)
        if is_sunday or is_privileged_feria:
            comms.append(tempora_file)
            comm_names.append(tempora_id or "")
        # Add kalendar commemorations
        for c in sanctoral.commemorations:
            if not c.suppressed and c.file_ref != "XXXXX":
                comms.append(f"Sancti/{c.file_ref}")
                comm_names.append(c.feast_name)

        return OccurrenceResult(
            winner_file=f"Sancti/{sanctoral.file_ref}",
            winner_rank=sanctoral.rank,
            winner_name=sanctoral.feast_name,
            is_sanctoral=True,
            is_requiem=_is_defunctorum(sanctoral.feast_name),
            commemorations=comms,
            commemoration_names=comm_names,
        )
