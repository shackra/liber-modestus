"""Custom line-level lexer for Divinum Officium documents.

This lexer classifies each non-empty line of a .txt file into a token type
based on its prefix/pattern and the current section context. The resulting
token stream is consumed by the Lark LALR(1) parser defined in
``divinum_officium.lark``.

The lexer operates line-by-line because the DO format is fundamentally
line-oriented: the first characters of each line determine its type.
"""

from __future__ import annotations

import re
from typing import Iterator, Optional

from lark.lexer import Lexer, Token

# ---------------------------------------------------------------------------
# Compiled regex patterns for line classification (order matters!)
# ---------------------------------------------------------------------------

# Section header: [Name] with optional (rubric condition)
_RE_SECTION_HEADER_RUBRIC = re.compile(r"^\s*\[([^\]]+)\]\s*\(([^)]+)\)\s*$")
_RE_SECTION_HEADER = re.compile(r"^\s*\[([^\]]+)\]\s*$")

# Cross-reference: @File:Section:Subs or @:Section
_RE_CROSS_REF = re.compile(r"^\s*@")

# Macro reference: $Name
_RE_MACRO_REF = re.compile(r"^\s*\$")

# Subroutine reference: &name or &name(args)
_RE_SUBROUTINE_REF = re.compile(r"^\s*&")

# Scripture ref / rubric instruction: !text
_RE_SCRIPTURE_REF = re.compile(r"^\s*!")

# Heading: # text or ##text (used in Ordo templates)
_RE_HEADING = re.compile(r"^\s*#")

# Separator: just "_" (possibly with whitespace)
_RE_SEPARATOR = re.compile(r"^\s*_\s*$")

# Short responsory breve: R.br. text
_RE_SHORT_RESP_BR = re.compile(r"^\s*R\.br\.\s")

# Dialog versicle: V. text (uppercase, with space after period)
_RE_DIALOG_VERSICLE = re.compile(r"^\s*V\.\s")

# Dialog response: R. text (uppercase, with space after period)
_RE_DIALOG_RESPONSE = re.compile(r"^\s*R\.\s")

# Versicle: v. text (lowercase)
_RE_VERSICLE = re.compile(r"^\s*v\.\s")

# Response continuation: r. text (lowercase)
_RE_RESPONSE = re.compile(r"^\s*r\.\s")

# Priest: S. text
_RE_PRIEST = re.compile(r"^\s*S\.\s")

# Minister: M. text
_RE_MINISTER = re.compile(r"^\s*M\.\s")

# Congregation: O. text
_RE_CONGREGATION = re.compile(r"^\s*O\.\s")

# Deacon: D. text
_RE_DEACON = re.compile(r"^\s*D\.\s")

# Rank value: must have at least 2 pairs of ;; (i.e., at least 3 fields)
# Format: Name;;Class;;Weight[;;CommonRef]
_RE_RANK_VALUE = re.compile(r"^[^;]*;;[^;]+;;")

# Conditional: line that is entirely a parenthesized condition
_RE_CONDITIONAL = re.compile(r"^\s*\([^)]+\)\s*$")

# Wait directive: waitN
_RE_WAIT = re.compile(r"^\s*wait\d+\s*$")

# Chant reference: {:id:} optionally followed by text
_RE_CHANT_REF = re.compile(r"^\s*\{:")

# Rule directive: Key=Value pattern that can appear outside [Rule] sections
# (e.g., in Rank's common ref). Inside [Rule] sections, ALL lines are directives.
_RE_RULE_DIRECTIVE_KEYVAL = re.compile(
    r"^\s*[\w\u00C0-\u024F][\w\u00C0-\u024F \-/]*=.+"
)

# Sections that contain rule directives rather than liturgical text
_RULE_SECTIONS = frozenset({"Rule"})


class DOLineLexer(Lexer):
    """Custom Lark lexer that tokenizes Divinum Officium documents line-by-line.

    Each non-empty, non-blank line is classified into exactly one token type.
    Blank lines are skipped entirely -- the grammar does not need them.

    The lexer tracks the current section name to provide context-dependent
    classification (e.g., lines in ``[Rule]`` sections are classified as
    rule directives rather than plain text).
    """

    __serialize_fields__ = ()

    def __init__(self, lexer_conf: object) -> None:
        # lexer_conf is provided by Lark but we don't need it
        pass

    def lex(self, data: str) -> Iterator[Token]:  # type: ignore[override]
        """Tokenize the input string into line-level tokens.

        Args:
            data: The full text content of a .txt file.

        Yields:
            Lark Token objects, one per significant line.
        """
        # Normalize line endings and remove BOM
        if data.startswith("\ufeff"):
            data = data[1:]

        lines = data.split("\n")
        current_section: Optional[str] = None

        for line_no, raw_line in enumerate(lines, start=1):
            # Strip trailing whitespace (but preserve leading for indentation)
            line = raw_line.rstrip()

            # Skip blank lines
            if not line or line.isspace():
                continue

            # Check if this is a section header and update context
            m = _RE_SECTION_HEADER_RUBRIC.match(line) or _RE_SECTION_HEADER.match(line)
            if m:
                current_section = m.group(1).strip()

            token = self._classify_line(line, line_no, current_section)
            if token is not None:
                yield token

    def _classify_line(
        self, line: str, line_no: int, current_section: Optional[str]
    ) -> Token | None:
        """Classify a single line into a token type.

        The order of checks matters: more specific patterns must be checked
        before more general ones.
        """
        stripped = line.strip()

        # Section header with rubric condition
        if _RE_SECTION_HEADER_RUBRIC.match(line):
            return Token(
                "SECTION_HEADER_WITH_RUBRIC",
                line,
                line=line_no,
                column=1,
            )

        # Section header without rubric
        if _RE_SECTION_HEADER.match(line):
            return Token("SECTION_HEADER", line, line=line_no, column=1)

        # Separator (must check before other single-char patterns)
        if _RE_SEPARATOR.match(line):
            return Token("SEPARATOR", line, line=line_no, column=1)

        # Cross-reference
        if _RE_CROSS_REF.match(line):
            return Token("CROSS_REF", line, line=line_no, column=1)

        # Macro reference
        if _RE_MACRO_REF.match(line):
            return Token("MACRO_REF", line, line=line_no, column=1)

        # Subroutine reference -- check &Gloria specifically
        if _RE_SUBROUTINE_REF.match(line):
            fn_name = stripped.lstrip("&").split("(")[0].strip()
            if fn_name == "Gloria":
                return Token("GLORIA_REF", line, line=line_no, column=1)
            return Token("SUBROUTINE_REF", line, line=line_no, column=1)

        # Scripture ref / rubric instruction
        if _RE_SCRIPTURE_REF.match(line):
            return Token("SCRIPTURE_REF", line, line=line_no, column=1)

        # Heading (# marker, used in Ordo templates)
        if _RE_HEADING.match(line):
            return Token("HEADING_LINE", line, line=line_no, column=1)

        # Chant reference
        if _RE_CHANT_REF.match(line):
            return Token("CHANT_REF_LINE", line, line=line_no, column=1)

        # Wait directive
        if _RE_WAIT.match(line):
            return Token("WAIT_DIRECTIVE", line, line=line_no, column=1)

        # Conditional (must check before dialog lines since "(sed..." starts with "(")
        if _RE_CONDITIONAL.match(line):
            return Token("CONDITIONAL_LINE", line, line=line_no, column=1)

        # Short responsory breve (must check before R.)
        if _RE_SHORT_RESP_BR.match(line):
            return Token("SHORT_RESPONSE_BR", line, line=line_no, column=1)

        # Dialog versicle V.
        if _RE_DIALOG_VERSICLE.match(line):
            return Token("DIALOG_VERSICLE", line, line=line_no, column=1)

        # Dialog response R.
        if _RE_DIALOG_RESPONSE.match(line):
            return Token("DIALOG_RESPONSE", line, line=line_no, column=1)

        # Versicle v.
        if _RE_VERSICLE.match(line):
            return Token("VERSICLE", line, line=line_no, column=1)

        # Response r.
        if _RE_RESPONSE.match(line):
            return Token("RESPONSE_LINE", line, line=line_no, column=1)

        # Priest S.
        if _RE_PRIEST.match(line):
            return Token("PRIEST_LINE", line, line=line_no, column=1)

        # Minister M.
        if _RE_MINISTER.match(line):
            return Token("MINISTER_LINE", line, line=line_no, column=1)

        # Congregation O.
        if _RE_CONGREGATION.match(line):
            return Token("CONGREGATION_LINE", line, line=line_no, column=1)

        # Deacon D.
        if _RE_DEACON.match(line):
            return Token("DEACON_LINE", line, line=line_no, column=1)

        # Rank value (contains ;; pattern with at least 3 fields)
        # Only match in Rank sections or preamble, not in Rule sections
        if current_section != "Rule" and _RE_RANK_VALUE.match(stripped):
            return Token("RANK_VALUE", line, line=line_no, column=1)

        # Rule directive (context-sensitive)
        # Inside a [Rule] section, ALL non-sigil lines are rule directives
        if current_section in _RULE_SECTIONS:
            return Token("RULE_DIRECTIVE", line, line=line_no, column=1)

        # Default: plain text
        return Token("TEXT_LINE", line, line=line_no, column=1)
