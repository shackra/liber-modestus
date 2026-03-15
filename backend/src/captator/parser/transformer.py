"""Lark Transformer that converts the parse tree into AST nodes.

The transformer takes the tree produced by the LALR(1) parser (which uses
tokens from the custom line-level lexer) and converts each node into the
appropriate AST dataclass from ``ast_nodes``.
"""

from __future__ import annotations

import re
from typing import Optional

from lark import Token, Transformer, v_args

from .ast_nodes import (
    ChantRef,
    ConditionalLine,
    CongregationLine,
    CrossRef,
    DeaconLine,
    DialogResponse,
    DialogVersicle,
    Document,
    GloriaRef,
    Heading,
    Line,
    LineKind,
    MacroRef,
    MinisterLine,
    PriestLine,
    RankValue,
    Response,
    RubricCondition,
    RuleDirective,
    ScriptureRef,
    Section,
    SectionHeader,
    Separator,
    ShortResponseBr,
    SubroutineRef,
    TextLine,
    Versicle,
    WaitDirective,
)

# ---------------------------------------------------------------------------
# Regex helpers for token value extraction
# ---------------------------------------------------------------------------

_RE_SECTION_HDR_RUBRIC = re.compile(r"^\s*\[([^\]]+)\]\s*\(([^)]+)\)\s*$")
_RE_SECTION_HDR = re.compile(r"^\s*\[([^\]]+)\]\s*$")

# Cross-reference: @[file][:section][:subs]
_RE_CROSS_REF = re.compile(
    r"^\s*@"
    r"([^:\n]*?)?"  # optional file
    r"(?::([^:\n]*?))?"  # optional :section
    r"(?::(.+))?"  # optional :substitutions
    r"\s*$"
)

_RE_SUBROUTINE = re.compile(r"^\s*&(\w+)(?:\(([^)]*)\))?\s*$")
_RE_WAIT = re.compile(r"^\s*wait(\d+)\s*$")
_RE_CHANT = re.compile(r"^\s*\{:([^:}]*):\}(.*)?$")
_RE_CONDITIONAL = re.compile(r"^\s*\(([^)]+)\)\s*$")


def _extract_body(line: str, prefix: str) -> str:
    """Strip a prefix (like 'v. ', 'V. ', 'R. ') from a line."""
    stripped = line.strip()
    if stripped.startswith(prefix):
        return stripped[len(prefix) :].strip()
    # Try without trailing space
    if stripped.startswith(prefix.rstrip()):
        return stripped[len(prefix.rstrip()) :].strip()
    return stripped


def _parse_rank_value(line: str) -> tuple[str, str, str, Optional[str]]:
    """Parse a rank value line into (name, class, weight, common_ref)."""
    parts = line.strip().split(";;")
    name = parts[0] if len(parts) > 0 else ""
    rank_class = parts[1] if len(parts) > 1 else ""
    weight = parts[2] if len(parts) > 2 else ""
    common = parts[3] if len(parts) > 3 else None
    # Strip trailing/leading whitespace from each field
    name = name.strip()
    rank_class = rank_class.strip()
    weight = weight.strip()
    if common is not None:
        common = common.strip()
        if common == "":
            common = None
    return name, rank_class, weight, common


def _parse_rule_directive(line: str) -> tuple[str, Optional[str]]:
    """Parse a rule directive into (keyword, optional value).

    For key=value directives, the value preserves trailing semicolons
    (e.g., ``Suffragium=Maria2;Papa;Ecclesia;;``).
    For standalone keywords, a single trailing ``;`` is stripped
    (e.g., ``ex Sancti/12-25m3;`` -> ``ex Sancti/12-25m3``).
    """
    stripped = line.strip()
    if "=" in stripped:
        key, _, val = stripped.partition("=")
        return key.strip(), val.strip()
    # Standalone keyword: strip trailing semicolons
    stripped = stripped.rstrip(";")
    return stripped.strip(), None


def _parse_cross_ref(line: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse a cross-reference line into (file, section, substitutions)."""
    stripped = line.strip()
    # Remove the leading @
    if stripped.startswith("@"):
        stripped = stripped[1:]

    if not stripped:
        return None, None, None

    # Split on colons, but be careful with substitutions that contain colons
    # The pattern is: file:section:subs
    # File can be empty (self-ref), section can be absent, subs can contain anything
    parts = stripped.split(":", 2)

    file_ref: Optional[str] = parts[0].strip() if parts[0].strip() else None
    section_ref: Optional[str] = None
    subs: Optional[str] = None

    if len(parts) > 1:
        section_ref = parts[1].strip() if parts[1].strip() else None
    if len(parts) > 2:
        subs = parts[2].strip() if parts[2].strip() else None

    return file_ref, section_ref, subs


def _parse_scripture_ref(line: str) -> tuple[str, bool, Optional[str]]:
    """Parse a scripture reference line.

    Returns (body, is_display_marker, display_marker).
    """
    stripped = line.strip()
    body = stripped[1:].strip() if stripped.startswith("!") else stripped

    # Check for display markers: !*S, !*R, !*D, !*nD, !*SnD, !*&func
    is_marker = False
    marker = None
    if body.startswith("*"):
        is_marker = True
        marker = body[1:].strip()

    return body, is_marker, marker


@v_args(inline=False)
class DOTransformer(Transformer):  # type: ignore[type-arg]
    """Transform the parse tree into a Document AST."""

    def start(self, items: list) -> Document:  # type: ignore[type-arg]
        preamble: list[Line] = []
        sections: list[Section] = []
        for item in items:
            if isinstance(item, list):
                # preamble returns a list of lines
                preamble = item
            elif isinstance(item, Section):
                sections.append(item)
        return Document(preamble=preamble, sections=sections)

    def preamble(self, items: list) -> list[Line]:  # type: ignore[type-arg]
        return [item for item in items if isinstance(item, Line)]

    def preamble_line(self, items: list) -> Line:  # type: ignore[type-arg]
        return items[0]

    def section(self, items: list) -> Section:  # type: ignore[type-arg]
        header = items[0]
        body = items[1] if len(items) > 1 else []
        return Section(header=header, body=body)

    def section_header(self, items: list) -> SectionHeader:  # type: ignore[type-arg]
        token = items[0]
        raw = str(token)

        if token.type == "SECTION_HEADER_WITH_RUBRIC":
            m = _RE_SECTION_HDR_RUBRIC.match(raw)
            if m:
                return SectionHeader(
                    kind=LineKind.SECTION_HEADER,
                    raw=raw,
                    line_number=token.line or 0,
                    name=m.group(1).strip(),
                    rubric=RubricCondition(expression=m.group(2).strip()),
                )
        else:
            m = _RE_SECTION_HDR.match(raw)
            if m:
                return SectionHeader(
                    kind=LineKind.SECTION_HEADER,
                    raw=raw,
                    line_number=token.line or 0,
                    name=m.group(1).strip(),
                    rubric=None,
                )

        # Fallback
        return SectionHeader(
            kind=LineKind.SECTION_HEADER, raw=raw, line_number=token.line or 0
        )

    def section_body(self, items: list) -> list[Line]:  # type: ignore[type-arg]
        return [item for item in items if isinstance(item, Line)]

    def body_line(self, items: list) -> Line:  # type: ignore[type-arg]
        return items[0]

    # --- Individual token transformations ---

    def CROSS_REF(self, token: Token) -> CrossRef:
        raw = str(token)
        file_ref, section_ref, subs = _parse_cross_ref(raw)
        return CrossRef(
            kind=LineKind.CROSS_REF,
            raw=raw,
            line_number=token.line or 0,
            file_ref=file_ref,
            section_ref=section_ref,
            substitutions=subs,
        )

    def MACRO_REF(self, token: Token) -> MacroRef:
        raw = str(token)
        name = raw.strip().lstrip("$").strip()
        return MacroRef(
            kind=LineKind.MACRO_REF,
            raw=raw,
            line_number=token.line or 0,
            macro_name=name,
        )

    def SUBROUTINE_REF(self, token: Token) -> SubroutineRef:
        raw = str(token)
        m = _RE_SUBROUTINE.match(raw)
        if m:
            return SubroutineRef(
                kind=LineKind.SUBROUTINE_REF,
                raw=raw,
                line_number=token.line or 0,
                function_name=m.group(1),
                arguments=m.group(2),
            )
        # Fallback: just strip the &
        name = raw.strip().lstrip("&").strip()
        return SubroutineRef(
            kind=LineKind.SUBROUTINE_REF,
            raw=raw,
            line_number=token.line or 0,
            function_name=name,
        )

    def GLORIA_REF(self, token: Token) -> GloriaRef:
        return GloriaRef(
            kind=LineKind.GLORIA_REF,
            raw=str(token),
            line_number=token.line or 0,
        )

    def SCRIPTURE_REF(self, token: Token) -> ScriptureRef:
        raw = str(token)
        body, is_marker, marker = _parse_scripture_ref(raw)
        return ScriptureRef(
            kind=LineKind.SCRIPTURE_REF,
            raw=raw,
            line_number=token.line or 0,
            body=body,
            is_display_marker=is_marker,
            display_marker=marker,
        )

    def HEADING_LINE(self, token: Token) -> Heading:
        raw = str(token)
        title = raw.strip().lstrip("#").strip()
        return Heading(
            kind=LineKind.HEADING,
            raw=raw,
            line_number=token.line or 0,
            title=title,
        )

    def SEPARATOR(self, token: Token) -> Separator:
        return Separator(
            kind=LineKind.SEPARATOR,
            raw=str(token),
            line_number=token.line or 0,
        )

    def VERSICLE(self, token: Token) -> Versicle:
        raw = str(token)
        return Versicle(
            kind=LineKind.VERSICLE,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "v. "),
        )

    def DIALOG_VERSICLE(self, token: Token) -> DialogVersicle:
        raw = str(token)
        return DialogVersicle(
            kind=LineKind.DIALOG_VERSICLE,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "V. "),
        )

    def DIALOG_RESPONSE(self, token: Token) -> DialogResponse:
        raw = str(token)
        return DialogResponse(
            kind=LineKind.DIALOG_RESPONSE,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "R. "),
        )

    def SHORT_RESPONSE_BR(self, token: Token) -> ShortResponseBr:
        raw = str(token)
        return ShortResponseBr(
            kind=LineKind.SHORT_RESPONSE_BR,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "R.br. "),
        )

    def RESPONSE_LINE(self, token: Token) -> Response:
        raw = str(token)
        return Response(
            kind=LineKind.RESPONSE,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "r. "),
        )

    def PRIEST_LINE(self, token: Token) -> PriestLine:
        raw = str(token)
        return PriestLine(
            kind=LineKind.PRIEST,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "S. "),
        )

    def MINISTER_LINE(self, token: Token) -> MinisterLine:
        raw = str(token)
        return MinisterLine(
            kind=LineKind.MINISTER,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "M. "),
        )

    def CONGREGATION_LINE(self, token: Token) -> CongregationLine:
        raw = str(token)
        return CongregationLine(
            kind=LineKind.CONGREGATION,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "O. "),
        )

    def DEACON_LINE(self, token: Token) -> DeaconLine:
        raw = str(token)
        return DeaconLine(
            kind=LineKind.DEACON,
            raw=raw,
            line_number=token.line or 0,
            body=_extract_body(raw, "D. "),
        )

    def RANK_VALUE(self, token: Token) -> RankValue:
        raw = str(token)
        name, rank_class, weight, common = _parse_rank_value(raw)
        return RankValue(
            kind=LineKind.RANK_VALUE,
            raw=raw,
            line_number=token.line or 0,
            display_name=name,
            rank_class=rank_class,
            weight=weight,
            common_ref=common,
        )

    def RULE_DIRECTIVE(self, token: Token) -> RuleDirective:
        raw = str(token)
        keyword, value = _parse_rule_directive(raw)
        return RuleDirective(
            kind=LineKind.RULE_DIRECTIVE,
            raw=raw,
            line_number=token.line or 0,
            keyword=keyword,
            value=value,
        )

    def CONDITIONAL_LINE(self, token: Token) -> ConditionalLine:
        raw = str(token)
        m = _RE_CONDITIONAL.match(raw)
        expr = m.group(1).strip() if m else raw.strip("() \t")
        return ConditionalLine(
            kind=LineKind.CONDITIONAL,
            raw=raw,
            line_number=token.line or 0,
            condition=RubricCondition(expression=expr),
        )

    def WAIT_DIRECTIVE(self, token: Token) -> WaitDirective:
        raw = str(token)
        m = _RE_WAIT.match(raw)
        seconds = int(m.group(1)) if m else 0
        return WaitDirective(
            kind=LineKind.WAIT_DIRECTIVE,
            raw=raw,
            line_number=token.line or 0,
            seconds=seconds,
        )

    def CHANT_REF_LINE(self, token: Token) -> ChantRef:
        raw = str(token)
        m = _RE_CHANT.match(raw)
        if m:
            return ChantRef(
                kind=LineKind.CHANT_REF,
                raw=raw,
                line_number=token.line or 0,
                chant_id=m.group(1) or "",
                suffix=m.group(2).strip() if m.group(2) else "",
            )
        return ChantRef(
            kind=LineKind.CHANT_REF,
            raw=raw,
            line_number=token.line or 0,
        )

    def TEXT_LINE(self, token: Token) -> TextLine:
        raw = str(token)
        return TextLine(
            kind=LineKind.TEXT,
            raw=raw,
            line_number=token.line or 0,
            body=raw.strip(),
        )

    # Handle tokens that arrive as-is (for section_header passthrough)
    def SECTION_HEADER(self, token: Token) -> Token:
        return token

    def SECTION_HEADER_WITH_RUBRIC(self, token: Token) -> Token:
        return token
