"""User-facing options for Mass configuration.

Returns structured lists of valid choices that a frontend can use to
populate dropdowns, radio groups, and similar controls.  Each option is
a ``(value, label)`` pair where *value* is the internal identifier (an
enum member or a string key) and *label* is a human-readable display
name.

Usage::

    from captator.options import get_mass_options

    opts = get_mass_options()
    for value, label in opts.rubrics:
        print(f"<option value='{value.name}'>{label}</option>")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sacrum.captator.resolver.config import MassType, MissalConfig, OrderVariant, Rubric

# ---------------------------------------------------------------------------
# Option item type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Option:
    """A single selectable option.

    Attributes:
        value: Internal identifier.  For enum-backed options this is the
            enum member's ``.name`` (e.g., ``"RUBRICAE_1960"``).  For
            string-backed options (languages, votives) it is the raw
            string key (e.g., ``"English"``, ``"C9"``).
        label: Human-readable display text (e.g.,
            ``"Rubrics 1960 (1962 Missal)"``).
        description: Optional longer description or tooltip text.
    """

    value: str
    label: str
    description: str = ""


# ---------------------------------------------------------------------------
# Complete options set
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MassOptions:
    """All user-configurable options for the Mass.

    Each field is a tuple of ``Option`` objects in display order.
    """

    rubrics: tuple[Option, ...] = ()
    """Available rubrical editions."""

    mass_types: tuple[Option, ...] = ()
    """Available Mass types (Solemn, Read, Requiem)."""

    orders: tuple[Option, ...] = ()
    """Available religious order variants."""

    languages: tuple[Option, ...] = ()
    """Available languages for prayer translations."""

    votives: tuple[Option, ...] = ()
    """Available votive Mass formularies (including "Hodie" = day's Mass)."""

    communes: tuple[Option, ...] = ()
    """Available commune references."""

    ordines: tuple[Option, ...] = ()
    """Available Ordo (canon/rite) variants.  Determines which fixed
    parts of the Mass template are used."""


# ---------------------------------------------------------------------------
# Static option data
# ---------------------------------------------------------------------------

_RUBRIC_OPTIONS: tuple[Option, ...] = (
    Option(
        value=Rubric.RUBRICAE_1960.name,
        label="Rubrics 1960 (1962 Missal)",
        description="Code of Rubrics promulgated by John XXIII.  "
        "The most common edition for the traditional Latin Mass.",
    ),
    Option(
        value=Rubric.RUBRICAE_1955.name,
        label="Reduced 1955",
        description="Simplified rubrics decreed by Pius XII in March 1955.  "
        "Suppresses most octaves and many vigils.",
    ),
    Option(
        value=Rubric.TRIDENT_1930.name,
        label="Divino Afflatu (~1930)",
        description="Post-Divino Afflatu rubrics with Pius XI additions, "
        "including the Feast of Christ the King (1925).",
    ),
    Option(
        value=Rubric.TRIDENT_1910.name,
        label="Divino Afflatu (1911)",
        description="Rubrics reformed by Pius X in 1911 (Divino Afflatu).  "
        "New psalter distribution for the Divine Office.",
    ),
    Option(
        value=Rubric.TRIDENT_1570.name,
        label="Tridentine (1570)",
        description="The original Tridentine Missal of Pius V.  "
        "Full octaves, all vigils, pre-Divino psalter.",
    ),
)

_MASS_TYPE_OPTIONS: tuple[Option, ...] = (
    Option(
        value=MassType.READ.name,
        label="Missa Lecta (Low Mass)",
        description="Read/Low Mass without singing.",
    ),
    Option(
        value=MassType.SOLEMN.name,
        label="Missa Solemnis (Solemn Mass)",
        description="Sung Mass with deacon and subdeacon.",
    ),
    Option(
        value=MassType.REQUIEM.name,
        label="Missa Defunctorum (Requiem)",
        description="Mass for the Dead.  No Gloria, no Alleluia, "
        "Requiem preface, Dies Irae sequence.",
    ),
)

_ORDER_OPTIONS: tuple[Option, ...] = (
    Option(
        value=OrderVariant.ROMAN.name,
        label="Roman Rite",
        description="Standard Roman Rite (secular and most religious orders).",
    ),
    Option(
        value=OrderVariant.MONASTIC.name,
        label="Monastic (Benedictine)",
        description="Benedictine monastic variant with proper calendar and hymns.",
    ),
    Option(
        value=OrderVariant.DOMINICAN.name,
        label="Dominican",
        description="Ordo Praedicatorum (Order of Preachers) variant.",
    ),
    Option(
        value=OrderVariant.CISTERCIAN.name,
        label="Cistercian",
        description="Cistercian variant with proper calendar.",
    ),
)

# Languages with display names.  The value is the directory name under
# missa/, the label is the user-facing name.  Sourced from missa.dialog
# [languages] section and the actual directories on disk.
_LANGUAGE_OPTIONS: tuple[Option, ...] = (
    Option(value="Latin", label="Latin"),
    Option(value="English", label="English"),
    Option(value="Espanol", label="Espanol"),
    Option(value="Francais", label="Francais"),
    Option(value="Deutsch", label="Deutsch"),
    Option(value="Italiano", label="Italiano"),
    Option(value="Polski", label="Polski"),
    Option(value="Portugues", label="Portugues"),
    Option(value="Magyar", label="Magyar"),
    Option(value="Nederlands", label="Nederlands"),
    Option(value="Bohemice", label="Bohemice"),
    Option(value="Cesky-Schaller", label="Cesky-Schaller"),
    Option(value="Ukrainian", label="Ukrainian"),
    Option(value="Vietnamice", label="Vietnamice"),
    Option(value="Dansk", label="Dansk"),
)

# Votive Masses.  value = commune/file code, label = display name.
# "Hodie" means "the Mass of the day" (no votive override).
_VOTIVE_OPTIONS: tuple[Option, ...] = (
    Option(value="Hodie", label="Hodie (Mass of the day)"),
    # Martyrs
    Option(value="C2", label="Unius Martyris Pontificis: Statuit"),
    Option(value="C2-1", label="Unius Martyris Pontificis: Sacerdotes Dei"),
    Option(value="C2a", label="Unius Martyris non Pontificis: In virtute"),
    Option(value="C2a-1", label="Unius Martyris non Pontificis: Laetabitur"),
    Option(value="C2b", label="Unius Martyris (Summi Pontificis): Si diligis"),
    Option(value="C2p", label="Unius Martyris Tempore Paschali: Protexisti"),
    Option(value="C3", label="Plurium Martyrum Pontificum: Intret in conspectu"),
    Option(value="C3a", label="Plurium Martyrum: Sapientiam Sanctorum"),
    Option(value="C3a-1", label="Plurium Martyrum: Salus autem"),
    Option(value="C3b", label="Plurium Martyrum (Summorum Pontificum): Si diligis"),
    Option(value="C3p", label="Plurium Martyrum Tempore Paschali: Sancti tui"),
    # Confessors
    Option(value="C4", label="Confessoris Pontificis: Statuit"),
    Option(value="C4-1", label="Confessoris Pontificis: Sacerdotes"),
    Option(value="C4a", label="Doctoris Pontificis: In medio"),
    Option(value="C4b", label="Confessoris (Summi Pontificis): Si diligis"),
    Option(value="C5", label="Confessoris non Pontificis: Os justi"),
    Option(value="C5-1", label="Confessoris non Pontificis: Justus"),
    Option(value="C5a", label="Doctoris non Pontificis: In medio"),
    Option(value="C5b", label="Abbatis: Os iusti (altera)"),
    # Virgins and holy women
    Option(value="C6", label="Unius Virginis et Martyris: Loquebar"),
    Option(value="C6-1", label="Unius Virginis et Martyris: Me exspectaverunt"),
    Option(value="C6a", label="Unius Virginis tantum: Dilexisti"),
    Option(value="C6a-1", label="Unius Virginis tantum: Vultum tuum"),
    Option(value="C6b", label="Plurium Virginum et Martyrum: Me exspectaverunt"),
    Option(value="C7", label="Unius non Virginis Martyris: Me exspectaverunt"),
    Option(value="C7a", label="Unius non Virginis nec Martyris: Cognovi"),
    Option(value="C7b", label="Plurium non Virginum Martyrum: Me exspectaverunt"),
    # Special
    Option(value="C8", label="Dedicationis Ecclesiae: Terribilis"),
    Option(value="C9", label="Defunctorum quotidianis: Requiem aeternam"),
    Option(value="C11", label="In Festis Beatae Mariae Virginis: Salve Sancte Parens"),
    Option(value="Coronatio", label="Votiva in Creatione et Coronatione Papae"),
    Option(value="Propaganda", label="Pro Propagatione Fidei"),
)

# Commune references.  value = file code, label = display name.
_COMMUNE_OPTIONS: tuple[Option, ...] = (
    Option(value="C1", label="Commune Apostolorum"),
    Option(value="C1a", label="Commune Evangelistarum"),
    Option(value="C1p", label="Commune Apostolorum tempore Paschali"),
    Option(value="C2", label="Commune Unius Martyris Pontificis (Statuit)"),
    Option(value="C2-1", label="Commune Unius Martyris Pontificis (Sacerdotes Dei)"),
    Option(value="C2a", label="Commune Unius Martyris non Pontificis (In virtute)"),
    Option(value="C2a-1", label="Commune Unius Martyris non Pontificis (Laetabitur)"),
    Option(value="C2b", label="Commune Unius Martyris Summi Pontificis (Si diligis)"),
    Option(value="C2p", label="Commune Unius Martyris tempore Paschali (Protexisti)"),
    Option(value="C3", label="Commune Plurium Martyrum Pontificum (Intret)"),
    Option(value="C3a", label="Commune Plurium Martyrum non Pontificum (Sapientiam)"),
    Option(
        value="C3a-1", label="Commune Plurium Martyrum non Pontificum (Salus autem)"
    ),
    Option(
        value="C3b", label="Commune Plurium Martyrum Summorum Pontificum (Si diligis)"
    ),
    Option(value="C3p", label="Commune Plurium Martyrum tempore Paschali (Sancti tui)"),
    Option(value="C4", label="Commune Confessoris Pontificis (Statuit)"),
    Option(value="C4-1", label="Commune Confessoris Pontificis (Sacerdotes Dei)"),
    Option(value="C4a", label="Commune Doctorum Pontificium (In medio)"),
    Option(value="C4b", label="Commune Confessorum Summorum Pontificum (Si diligis)"),
    Option(value="C5", label="Commune Confessoris non Pontificis (Os justi)"),
    Option(value="C5-1", label="Commune Confessoris non Pontificis (Justus)"),
    Option(value="C5a", label="Commune Doctoris non Pontificis (In medio)"),
    Option(value="C5b", label="Commune Abbatum (Os justi altera)"),
    Option(value="C6", label="Commune Unius Virginis Martyris (Loquebar)"),
    Option(value="C6-1", label="Commune Unius Virginis Martyris (Me expectaverunt)"),
    Option(value="C6a", label="Commune Unius Virginis tantum (Dilexisti)"),
    Option(value="C6a-1", label="Commune Unius Virginis tantum (Vultum tuum)"),
    Option(value="C6b", label="Commune Plurium Virginum Martyrum (Me expectaverunt)"),
    Option(value="C7", label="Commune Unius non Virginis Martyris (Me expectaverunt)"),
    Option(value="C7a", label="Commune Unius non Virginis nec Martyris (Cognovi)"),
    Option(
        value="C7b", label="Commune Plurium non Virginum Martyrum (Me expectaverunt)"
    ),
    Option(value="C8", label="Commune Dedicationis Ecclesiae"),
    Option(value="C9", label="Officium Defunctorum"),
    Option(value="C10", label="Beata Maria in Sabbato"),
    Option(value="C11", label="Commune Beatae Mariae Virginis"),
)

# Ordo (canon / rite) variants.  value = filename stem, label = display name.
_ORDO_OPTIONS: tuple[Option, ...] = (
    Option(
        value="Ordo",
        label="Roman Rite (Tridentine / 1962)",
        description="Standard Ordo Missae of the Roman Rite as codified in "
        "the Missale Romanum from 1570 through 1962.",
    ),
    Option(
        value="OrdoOP",
        label="Dominican Rite",
        description="Ordo Missae of the Order of Preachers (O.P.).",
    ),
    Option(
        value="OrdoS",
        label="Sarum Use",
        description="Medieval English variant of the Roman Rite " "(Use of Salisbury).",
    ),
    Option(
        value="OrdoA",
        label="Ambrosian Rite",
        description="Rite of the Archdiocese of Milan.",
    ),
    Option(
        value="OrdoM",
        label="Mozarabic Rite",
        description="Hispano-Visigothic Rite (Rito Mozarabe).",
    ),
    Option(
        value="Ordo67",
        label="1965-1967 Transitional",
        description="Transitional Ordo with progressive reforms "
        "between the 1962 and 1970 Missals.",
    ),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_mass_options() -> MassOptions:
    """Return all user-configurable options for the Mass.

    The returned ``MassOptions`` contains pre-built tuples of ``Option``
    objects for every configurable dimension.  Each ``Option`` has a
    ``value`` (for internal use) and a ``label`` (for display).

    This function requires no arguments and no file access -- all data
    is compiled statically from the known Divinum Officium configuration.

    Returns:
        A ``MassOptions`` instance with all option sets.
    """
    return MassOptions(
        rubrics=_RUBRIC_OPTIONS,
        mass_types=_MASS_TYPE_OPTIONS,
        orders=_ORDER_OPTIONS,
        languages=_LANGUAGE_OPTIONS,
        votives=_VOTIVE_OPTIONS,
        communes=_COMMUNE_OPTIONS,
        ordines=_ORDO_OPTIONS,
    )


def get_languages_from_disk(missa_path: str | Path) -> tuple[Option, ...]:
    """Discover available languages by scanning the ``missa/`` directory.

    Unlike ``get_mass_options().languages`` (which returns a static list),
    this function checks which language directories actually exist on
    disk.  Useful for validating that the data files are present.

    Args:
        missa_path: Path to the parent of the language directories
            (e.g., ``".../web/www/missa"``).  Each immediate subdirectory
            that contains an ``Ordo/`` folder is treated as a language.

    Returns:
        A tuple of ``Option`` objects for each discovered language,
        sorted alphabetically with Latin first.
    """
    base = Path(missa_path)
    if not base.is_dir():
        return ()

    langs: list[Option] = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / "Ordo").is_dir():
            langs.append(Option(value=child.name, label=child.name))

    # Move Latin to the front if present
    latin = [o for o in langs if o.value == "Latin"]
    others = [o for o in langs if o.value != "Latin"]
    return tuple(latin + others)
