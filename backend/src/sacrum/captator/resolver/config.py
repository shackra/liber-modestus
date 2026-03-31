"""Configuration types for the Divinum Officium document resolver.

These enums and dataclass define the "missal configuration" that determines
which rubric variants, Mass type sections, and religious order variants
are active when resolving a document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Rubric(Enum):
    """Rubrical edition of the missal.

    Each value maps to a version string that is tested by ``(rubrica ...)``
    conditions.  The Perl codebase uses regex matching against these strings,
    so the string values are chosen to match the patterns found in the data.
    """

    TRIDENT_1570 = "Trident 1570"
    """The original Tridentine rubrics (1570 Missal of Pius V)."""

    TRIDENT_1910 = "Trident 1910"
    """Divino Afflatu rubrics (Pius X, 1911)."""

    TRIDENT_1930 = "Trident 1930"
    """Post-Divino Afflatu rubrics with Pius XI additions."""

    RUBRICAE_1955 = "Rubrics 1955"
    """Simplified rubrics of 1955 (Pius XII, decree of March 1955)."""

    RUBRICAE_1960 = "Rubrics 1960"
    """Rubrics of 1960 / Code of Rubrics (John XXIII, 1962 Missal)."""

    def matches(self, pattern: str) -> bool:
        """Test if this rubric's version string matches a regex pattern.

        This replicates the Perl ``vero()`` behavior where rubric predicates
        are treated as regexes tested against ``$version``.
        """
        import re

        return bool(re.search(pattern, self.value, re.IGNORECASE))


class MassType(Enum):
    """Type of Mass celebration, affects ``!*S``/``!*R``/``!*D`` markers."""

    SOLEMN = auto()
    """Missa Solemnis / Missa Cantata (sung Mass)."""

    READ = auto()
    """Missa Lecta (low/read Mass)."""

    REQUIEM = auto()
    """Missa Defunctorum (Mass for the Dead / Requiem)."""


class OrderVariant(Enum):
    """Religious order variant for directory/file selection.

    Determines which subdirectory suffix to use when looking up files:
    e.g., ``SanctiM/``, ``SanctiOP/``, ``SanctiCist/``.
    """

    ROMAN = auto()
    """Standard Roman Rite (no suffix)."""

    MONASTIC = auto()
    """Monastic (Benedictine) variant — suffix ``M``."""

    DOMINICAN = auto()
    """Dominican (Order of Preachers) variant — suffix ``OP``."""

    CISTERCIAN = auto()
    """Cistercian variant — suffix ``Cist``."""

    @property
    def dir_suffix(self) -> str:
        """Return the directory suffix for this variant."""
        match self:
            case OrderVariant.ROMAN:
                return ""
            case OrderVariant.MONASTIC:
                return "M"
            case OrderVariant.DOMINICAN:
                return "OP"
            case OrderVariant.CISTERCIAN:
                return "Cist"

    @property
    def version_marker(self) -> str:
        """Return the version string fragment that conditions test against."""
        match self:
            case OrderVariant.ROMAN:
                return ""
            case OrderVariant.MONASTIC:
                return "Monastic"
            case OrderVariant.DOMINICAN:
                return "Ordo Praedicatorum"
            case OrderVariant.CISTERCIAN:
                return "Cisterciensis"


@dataclass(frozen=True)
class MissalConfig:
    """Complete missal configuration for document resolution.

    This is the central configuration object that drives all conditional
    evaluation during document resolution.
    """

    rubric: Rubric = Rubric.RUBRICAE_1960
    """The rubrical edition to use."""

    mass_type: MassType = MassType.READ
    """The type of Mass celebration."""

    order: OrderVariant = OrderVariant.ROMAN
    """The religious order variant."""

    language: str = "Latin"
    """Language for prayer/macro expansion (e.g., 'Latin', 'English',
    'Espanol', 'Francais'). The language name must match a directory
    name under ``web/www/missa/``.  Latin is always the base layer;
    the chosen language overrides section-by-section."""

    day_of_week: int = 1
    """Day of week, 1-indexed (1=Sunday, ..., 7=Saturday)."""

    tempus_id: str = ""
    """Liturgical period identifier (e.g., 'Adventus', 'Quadragesimæ',
    'post Pentecosten'). Used for ``(tempore ...)`` conditions.
    Set by the caller based on the liturgical calendar."""

    dayname: str = ""
    """Day name code (e.g., 'Adv1-0', 'Pasc3-2', 'Pent07-3').
    Used for ``(die ...)`` conditions."""

    commune: str = ""
    """Current commune file in use (e.g., 'C1', 'C4b').
    Used for ``(commune ...)`` conditions."""

    votive: str = ""
    """Votive Mass identifier, if any.
    Used for ``(votiva ...)`` conditions and Requiem detection."""

    @property
    def version_string(self) -> str:
        """Build the full version string tested by ``(rubrica ...)`` conditions.

        Combines the rubric edition and the order variant marker.
        """
        parts = [self.rubric.value]
        if self.order.version_marker:
            parts.append(self.order.version_marker)
        return " ".join(parts)

    @property
    def is_solemn(self) -> bool:
        return self.mass_type == MassType.SOLEMN

    @property
    def is_requiem(self) -> bool:
        return self.mass_type == MassType.REQUIEM or bool(
            self.votive and ("Defunct" in self.votive or "C9" in self.votive)
        )
