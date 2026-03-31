"""Mass assembly: combines the Ordo (fixed parts) with the day's Propers.

The Ordo template (``Ordo.txt``, ``OrdoOP.txt``, etc.) is a complete
linear rendering of the Mass with ``&name`` placeholders where the
day's proper texts are inserted.  This module parses the Ordo template,
resolves the ``&`` insertion points using the proper sections from a
resolved ``Document``, selects the correct Preface and Communicantes
based on the liturgical season, and returns a unified ``Document``
representing the complete Mass from start to finish.

Usage::

    from captator.assembly import assemble_mass

    complete = assemble_mass(
        propers=resolved_document,
        config=config,
        missa_path="path/to/missa/Latin",
        ordo="Ordo",           # or "OrdoOP", "OrdoS", etc.
    )
    for section in complete.sections:
        print(f"[{section.header.name}]")
        for line in section.body:
            print(f"  {line.raw}")
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from sacrum.captator.parser import parse_file
from sacrum.captator.parser.ast_nodes import (
    Document,
    GloriaRef,
    Line,
    LineKind,
    MacroRef,
    RuleDirective,
    Section,
    SectionHeader,
    SubroutineRef,
    TextLine,
)
from sacrum.captator.resolver import MissalConfig, resolve
from sacrum.captator.resolver.config import Rubric

# ---------------------------------------------------------------------------
# Proper section mapping: &subroutine -> [SectionName]
# ---------------------------------------------------------------------------

# Maps the &name subroutine calls found in Ordo.txt to the section name
# they pull from the day's proper file.
_PROPER_MAP: dict[str, str] = {
    "introitus": "Introitus",
    "collect": "Oratio",
    "lectio": "Lectio",
    "graduale": "Graduale",
    "evangelium": "Evangelium",
    "offertorium": "Offertorium",
    "secreta": "Secreta",
    "communio": "Communio",
    "postcommunio": "Postcommunio",
}

# Sections that may appear under alternate names in the proper
_PROPER_FALLBACKS: dict[str, list[str]] = {
    "Graduale": ["GradualeF", "Tractus", "Sequentia"],
}


# ---------------------------------------------------------------------------
# Preface selection: Rule's Prefatio= key -> Prefationes.txt section name
# ---------------------------------------------------------------------------

# The [Rule] section in a proper file may contain "Prefatio=Key".
# This maps to a section in Prefationes.txt.
# If no Prefatio= rule, the preface is selected by liturgical season.

_SEASON_PREFACE: dict[str, str] = {
    "Adventus": "Adv",
    "Nativitatis": "Nat",
    "post Epiphaniam": "Epi",
    "Quadragesimae": "Quad",
    "Passionis": "Quad5",
    "Octava Paschae": "Pasch",
    "post Octavam Paschae": "Pasch",
    "post Pentecosten": "Communis",
    "Septuagesimae": "Communis",
}


def _get_preface_key(propers: Document, config: MissalConfig) -> str:
    """Determine the Preface section key for this Mass.

    Priority:
    1. Explicit ``Prefatio=Key`` in the [Rule] section of the propers.
    2. Season-based default from the tempus_id.
    3. ``Communis`` as ultimate fallback.
    """
    rule = propers.get_section("Rule")
    if rule:
        for line in rule.body:
            if isinstance(line, RuleDirective) and line.keyword == "Prefatio":
                return line.value or "Communis"

    return _SEASON_PREFACE.get(config.tempus_id, "Communis")


def _get_communicantes_key(config: MissalConfig) -> str:
    """Determine the Communicantes section key.

    The 1962 Missal adds St. Joseph to the Communicantes; earlier
    editions do not.  Seasonal variants exist for Christmas, Epiphany,
    Easter, Ascension, and Pentecost.
    """
    is_1962 = "196" in config.rubric.value

    season_map: dict[str, str] = {
        "Nativitatis": "Nat",
        "post Epiphaniam": "Epi",
        "Octava Paschae": "Pasc",
        "post Octavam Paschae": "",  # only during the octave
    }

    # Ascension and Pentecost are detected by dayname patterns
    dayname = config.dayname or ""
    if dayname.startswith("Pasc6-") or dayname == "Pasc5-4":
        # Ascension day through its octave
        season_key = "Asc"
    elif dayname.startswith("Pasc7-"):
        season_key = "Pent"
    else:
        season_key = season_map.get(config.tempus_id, "")

    if season_key:
        return f"C-{season_key}1962" if is_1962 else f"C-{season_key}"

    return "C-common1962" if is_1962 else "C-common"


def _get_hanc_igitur_key(config: MissalConfig) -> Optional[str]:
    """Determine the Hanc igitur section key (if any).

    Special Hanc igitur is said only during the Easter and Pentecost
    octaves.  Returns None if the common Hanc igitur should be used
    (which is already inline in the Ordo template).
    """
    dayname = config.dayname or ""
    if dayname.startswith("Pasc0-") or dayname.startswith("Pasc7-"):
        return "H-Pent"
    return None


# ---------------------------------------------------------------------------
# Ordo + Prefationes loading (cached)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=16)
def _load_prefationes(path: str) -> dict[str, list[Line]]:
    """Load Prefationes.txt into a section-name -> lines dict."""
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        doc = parse_file(str(p))
    except Exception:
        return {}
    return {s.header.name: s.body for s in doc.sections}


@lru_cache(maxsize=16)
def _load_ordo_raw(path: str) -> Document:
    """Load and parse an Ordo template file."""
    return parse_file(path)


# ---------------------------------------------------------------------------
# Proper section extraction
# ---------------------------------------------------------------------------


def _get_proper_lines(propers: Document, section_name: str) -> list[Line]:
    """Extract lines for a proper section, trying fallback names."""
    section = propers.get_section(section_name)
    if section and section.body:
        return section.body

    for fallback in _PROPER_FALLBACKS.get(section_name, []):
        section = propers.get_section(fallback)
        if section and section.body:
            return section.body

    return []


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _substitute_line(
    line: Line,
    propers: Document,
    prefationes: dict[str, list[Line]],
    preface_key: str,
    communicantes_key: str,
    hanc_igitur_key: Optional[str],
) -> list[Line]:
    """Replace a single ``&`` subroutine line with proper content.

    Returns the replacement lines, or the original line unchanged if
    no substitution applies.
    """
    if isinstance(line, SubroutineRef):
        name = line.function_name

        # Proper insertion
        if name in _PROPER_MAP:
            section_name = _PROPER_MAP[name]
            lines = _get_proper_lines(propers, section_name)
            if lines:
                return lines
            return [line]

        # Preface
        if name == "prefatio":
            pref = prefationes.get(preface_key)
            if pref:
                return pref
            pref = prefationes.get("Communis")
            return pref if pref else [line]

        # Communicantes
        if name == "communicantes":
            comm = prefationes.get(communicantes_key)
            return comm if comm else [line]

        # Hanc igitur
        if name == "hancigitur":
            if hanc_igitur_key:
                hi = prefationes.get(hanc_igitur_key)
                return hi if hi else []
            return []  # No special Hanc igitur -- the common one is inline

        # Communio Populi (Communion of the Faithful rite)
        if name == "Communio_Populi":
            return [line]  # Keep as marker for now

        # itemissaest, Ultimaev, Vidiaquam -- these are handled by
        # the resolver's &subroutine expansion from Prayers.txt.
        # If they survived to this point, keep them.
        return [line]

    if isinstance(line, GloriaRef):
        # &Gloria is already expanded by the resolver; if it survived,
        # keep it as-is.
        return [line]

    return [line]


def assemble_mass(
    propers: Document,
    config: MissalConfig,
    missa_path: str | Path,
    ordo: str = "Ordo",
) -> Document:
    """Assemble a complete Mass by combining the Ordo template with propers.

    Args:
        propers: A resolved ``Document`` containing the day's proper
            sections (Introitus, Oratio, Lectio, etc.).
        config: The missal configuration (used for preface/communicantes
            selection and display marker filtering).
        missa_path: Path to the language-specific missa directory
            (e.g., ``".../missa/Latin"``).
        ordo: The Ordo template stem (``"Ordo"``, ``"OrdoOP"``,
            ``"OrdoS"``, ``"OrdoA"``, ``"OrdoM"``, ``"Ordo67"``).

    Returns:
        A ``Document`` whose preamble + sections contain the entire Mass
        from Prayers at the Foot of the Altar through the Last Gospel,
        with the day's propers inserted at the correct positions.
    """
    base = Path(missa_path)

    # Load the Ordo template
    ordo_path = base / "Ordo" / f"{ordo}.txt"
    if not ordo_path.is_file():
        # Fallback to standard Ordo
        ordo_path = base / "Ordo" / "Ordo.txt"

    ordo_doc = _load_ordo_raw(str(ordo_path))

    # Resolve the Ordo template (evaluate conditions, expand Prayers.txt
    # macros, filter display markers)
    resolved_ordo = resolve(ordo_doc, config, str(base))

    # Load Prefationes
    prefationes = _load_prefationes(str(base / "Ordo" / "Prefationes.txt"))

    # Determine liturgical keys
    preface_key = _get_preface_key(propers, config)
    communicantes_key = _get_communicantes_key(config)
    hanc_igitur_key = _get_hanc_igitur_key(config)

    # Walk the resolved Ordo and substitute & calls with proper content
    new_preamble = _substitute_lines(
        resolved_ordo.preamble,
        propers,
        prefationes,
        preface_key,
        communicantes_key,
        hanc_igitur_key,
    )

    new_sections: list[Section] = []
    for section in resolved_ordo.sections:
        new_body = _substitute_lines(
            section.body,
            propers,
            prefationes,
            preface_key,
            communicantes_key,
            hanc_igitur_key,
        )
        new_sections.append(Section(header=section.header, body=new_body))

    return Document(preamble=new_preamble, sections=new_sections)


def _substitute_lines(
    lines: list[Line],
    propers: Document,
    prefationes: dict[str, list[Line]],
    preface_key: str,
    communicantes_key: str,
    hanc_igitur_key: Optional[str],
) -> list[Line]:
    """Apply substitutions to a list of lines."""
    result: list[Line] = []
    for line in lines:
        result.extend(
            _substitute_line(
                line,
                propers,
                prefationes,
                preface_key,
                communicantes_key,
                hanc_igitur_key,
            )
        )
    return result
