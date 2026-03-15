"""AST node types for Divinum Officium parsed documents.

These dataclasses represent the structured output of parsing a .txt
file from the Divinum Officium project. The hierarchy is:

    Document
    ├── preamble: list[Line]  (lines before the first section)
    └── sections: list[Section]
        ├── header: SectionHeader
        └── body: list[Line]

Each Line is a tagged union (via subclasses) representing the different
line types found in the format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

# ---------------------------------------------------------------------------
# Line types
# ---------------------------------------------------------------------------


class LineKind(Enum):
    """Classification of a line in a Divinum Officium document."""

    SECTION_HEADER = auto()
    CROSS_REF = auto()
    MACRO_REF = auto()
    SUBROUTINE_REF = auto()
    SCRIPTURE_REF = auto()
    HEADING = auto()
    SEPARATOR = auto()
    VERSICLE = auto()
    DIALOG_VERSICLE = auto()
    DIALOG_RESPONSE = auto()
    SHORT_RESPONSE_BR = auto()
    RESPONSE = auto()
    PRIEST = auto()
    MINISTER = auto()
    CONGREGATION = auto()
    DEACON = auto()
    RANK_VALUE = auto()
    RULE_DIRECTIVE = auto()
    CONDITIONAL = auto()
    WAIT_DIRECTIVE = auto()
    CHANT_REF = auto()
    GLORIA_REF = auto()
    TEXT = auto()


# ---------------------------------------------------------------------------
# Base line
# ---------------------------------------------------------------------------


@dataclass
class Line:
    """Base class for all line types."""

    kind: LineKind
    raw: str
    line_number: int = 0


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------


@dataclass
class RubricCondition:
    """A rubric condition attached to a section header or inline.

    The expression text is kept as-is (e.g. "rubrica 196 aut rubrica 1955")
    for downstream evaluation.
    """

    expression: str


@dataclass
class SectionHeader(Line):
    """A section header like ``[Rank]`` or ``[Ant Vespera] (rubrica 1960)``."""

    name: str = ""
    rubric: Optional[RubricCondition] = None

    def __post_init__(self) -> None:
        self.kind = LineKind.SECTION_HEADER


# ---------------------------------------------------------------------------
# Cross-reference
# ---------------------------------------------------------------------------


@dataclass
class CrossRef(Line):
    """A cross-reference like ``@Tempora/Nat2-0:Evangelium:s/old/new/``."""

    file_ref: Optional[str] = None
    section_ref: Optional[str] = None
    substitutions: Optional[str] = None

    def __post_init__(self) -> None:
        self.kind = LineKind.CROSS_REF

    @property
    def is_self_ref(self) -> bool:
        """True if this is a self-reference (``@:SectionName``)."""
        return self.file_ref is None or self.file_ref == ""


# ---------------------------------------------------------------------------
# Macro reference ($)
# ---------------------------------------------------------------------------


@dataclass
class MacroRef(Line):
    """A macro/prayer reference like ``$Per Dominum`` or ``$Qui tecum``."""

    macro_name: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.MACRO_REF


# ---------------------------------------------------------------------------
# Subroutine reference (&)
# ---------------------------------------------------------------------------


@dataclass
class SubroutineRef(Line):
    """A subroutine call like ``&Gloria`` or ``&psalm(94)``."""

    function_name: str = ""
    arguments: Optional[str] = None

    def __post_init__(self) -> None:
        self.kind = LineKind.SUBROUTINE_REF


# ---------------------------------------------------------------------------
# Scripture reference / Rubric instruction (!)
# ---------------------------------------------------------------------------


@dataclass
class ScriptureRef(Line):
    """A line starting with ``!``.

    This covers:
    - Scripture citations: ``!Ps 24:1-3``
    - Rubrical instructions: ``!Oratio propria.``
    - Conditional display markers: ``!*S``, ``!*R``, ``!*D``, ``!*nD``, ``!*SnD``
    - Subroutine hooks: ``!*&GloriaM``
    """

    body: str = ""
    is_display_marker: bool = False
    display_marker: Optional[str] = None

    def __post_init__(self) -> None:
        self.kind = LineKind.SCRIPTURE_REF


# ---------------------------------------------------------------------------
# Heading (#)
# ---------------------------------------------------------------------------


@dataclass
class Heading(Line):
    """A structural heading like ``# Introitus`` or ``#Psalmi``."""

    title: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.HEADING


# ---------------------------------------------------------------------------
# Separator (_)
# ---------------------------------------------------------------------------


@dataclass
class Separator(Line):
    """A separator line (``_``)."""

    def __post_init__(self) -> None:
        self.kind = LineKind.SEPARATOR


# ---------------------------------------------------------------------------
# Versicle / Response / Dialog lines
# ---------------------------------------------------------------------------


@dataclass
class Versicle(Line):
    """An initial verse line: ``v. Text``."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.VERSICLE


@dataclass
class DialogVersicle(Line):
    """A liturgical dialog versicle: ``V. Text``."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.DIALOG_VERSICLE


@dataclass
class DialogResponse(Line):
    """A liturgical dialog response: ``R. Text``."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.DIALOG_RESPONSE


@dataclass
class ShortResponseBr(Line):
    """A short responsory breve: ``R.br. Text * Division``."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.SHORT_RESPONSE_BR


@dataclass
class Response(Line):
    """A response continuation: ``r. Text`` (lowercase)."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.RESPONSE


# ---------------------------------------------------------------------------
# Mass dialog roles
# ---------------------------------------------------------------------------


@dataclass
class PriestLine(Line):
    """Priest's part: ``S. Text`` (Sacerdos)."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.PRIEST


@dataclass
class MinisterLine(Line):
    """Minister's part: ``M. Text``."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.MINISTER


@dataclass
class CongregationLine(Line):
    """Congregation's part: ``O. Text`` (Omnes)."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.CONGREGATION


@dataclass
class DeaconLine(Line):
    """Deacon's part: ``D. Text``."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.DEACON


# ---------------------------------------------------------------------------
# Rank value
# ---------------------------------------------------------------------------


@dataclass
class RankValue(Line):
    """A rank value line with ``;;``-separated fields.

    Format: ``DisplayName;;RankClass;;NumericWeight;;CommonRef``
    """

    display_name: str = ""
    rank_class: str = ""
    weight: str = ""
    common_ref: Optional[str] = None

    def __post_init__(self) -> None:
        self.kind = LineKind.RANK_VALUE


# ---------------------------------------------------------------------------
# Rule directive
# ---------------------------------------------------------------------------


@dataclass
class RuleDirective(Line):
    """A rule directive from the ``[Rule]`` section.

    Examples: ``Gloria``, ``Credo``, ``Prefatio=Nat``, ``ex Sancti/12-25;``
    """

    keyword: str = ""
    value: Optional[str] = None

    def __post_init__(self) -> None:
        self.kind = LineKind.RULE_DIRECTIVE


# ---------------------------------------------------------------------------
# Conditional (inline rubric)
# ---------------------------------------------------------------------------


@dataclass
class ConditionalLine(Line):
    """An inline conditional like ``(rubrica tridentina)`` or ``(sed rubrica 196)``."""

    condition: RubricCondition = field(default_factory=lambda: RubricCondition(""))

    def __post_init__(self) -> None:
        self.kind = LineKind.CONDITIONAL


# ---------------------------------------------------------------------------
# Wait directive
# ---------------------------------------------------------------------------


@dataclass
class WaitDirective(Line):
    """A display timing directive like ``wait10``."""

    seconds: int = 0

    def __post_init__(self) -> None:
        self.kind = LineKind.WAIT_DIRECTIVE


# ---------------------------------------------------------------------------
# Chant reference
# ---------------------------------------------------------------------------


@dataclass
class ChantRef(Line):
    """A GABC chant reference like ``{:H-VespFeria:}v. Text``."""

    chant_id: str = ""
    suffix: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.CHANT_REF


# ---------------------------------------------------------------------------
# Gloria reference (&Gloria within Introitus)
# ---------------------------------------------------------------------------


@dataclass
class GloriaRef(Line):
    """Shorthand ``&Gloria`` reference (Gloria Patri doxology)."""

    def __post_init__(self) -> None:
        self.kind = LineKind.GLORIA_REF


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------


@dataclass
class TextLine(Line):
    """A plain text line (prayer text, readings, etc.)."""

    body: str = ""

    def __post_init__(self) -> None:
        self.kind = LineKind.TEXT


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------


@dataclass
class Section:
    """A document section with a header and body lines."""

    header: SectionHeader = field(
        default_factory=lambda: SectionHeader(kind=LineKind.SECTION_HEADER, raw="")
    )
    body: list[Line] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Document (top-level AST)
# ---------------------------------------------------------------------------


@dataclass
class Document:
    """A fully parsed Divinum Officium document."""

    preamble: list[Line] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    def get_section(self, name: str) -> Optional[Section]:
        """Find the first section with the given name (no rubric condition)."""
        for s in self.sections:
            if s.header.name == name and s.header.rubric is None:
                return s
        return None

    def get_sections(self, name: str) -> list[Section]:
        """Find all sections with the given name (including rubric variants)."""
        return [s for s in self.sections if s.header.name == name]

    def get_section_names(self) -> list[str]:
        """Return unique section names in order of appearance."""
        seen: set[str] = set()
        result: list[str] = []
        for s in self.sections:
            if s.header.name not in seen:
                seen.add(s.header.name)
                result.append(s.header.name)
        return result
