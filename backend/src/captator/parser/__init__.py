"""Parser for Divinum Officium .txt document files.

This module provides:
- ``Tokenizer``: Classifies lines of a document into typed tokens.
- ``parse``: Parses a document string into a ``Document`` AST.

Architecture:
    1. A custom line-level lexer (``DOLineLexer``) classifies each line
       by its prefix/pattern into a token type.
    2. A Lark LALR(1) parser consumes the token stream and builds a
       parse tree according to the grammar in ``divinum_officium.lark``.
    3. A Transformer (``DOTransformer``) converts the parse tree into
       a typed AST of dataclass nodes (``Document``, ``Section``, etc.).

The format is fundamentally line-oriented, making the custom-lexer +
LALR(1) parser combination ideal: the lexer handles the "what type of
line is this?" question (which is regex-based), while the parser handles
the structural "how do sections nest?" question (which is context-free).

LALR(1) was chosen over other LR variants because:
- The grammar has no ambiguity at the structural level (sections are
  clearly delimited by ``[Header]`` lines).
- LALR(1) is the most efficient parser type that handles all the
  lookahead needed (just 1 token suffices).
- Lark defaults to LALR(1) and it generates the smallest/fastest tables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from lark import Lark, Token

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
from .lexer import DOLineLexer
from .transformer import DOTransformer

# ---------------------------------------------------------------------------
# Grammar loading
# ---------------------------------------------------------------------------

_GRAMMAR_PATH = Path(__file__).parent / "divinum_officium.lark"

_parser = Lark(
    _GRAMMAR_PATH.read_text(encoding="utf-8"),
    parser="lalr",
    lexer=DOLineLexer,
)


# ---------------------------------------------------------------------------
# Tokenizer (line-level classification)
# ---------------------------------------------------------------------------


class Tokenizer(Sequence[Token]):
    """Tokenize a Divinum Officium document into classified line tokens.

    This is a thin wrapper around the custom lexer that provides a
    sequence interface for easy inspection and testing.

    Usage::

        tokens = Tokenizer(text)
        for token in tokens:
            print(token.type, token.value)
        print(len(tokens))
    """

    def __init__(self, text: str) -> None:
        lexer = DOLineLexer(None)
        self._tokens: list[Token] = list(lexer.lex(text))

    def __getitem__(self, index):  # type: ignore[override]
        return self._tokens[index]

    def __len__(self) -> int:
        return len(self._tokens)

    def __repr__(self) -> str:
        return f"Tokenizer({len(self._tokens)} tokens)"

    def types(self) -> list[str]:
        """Return the list of token type names."""
        return [t.type for t in self._tokens]


# ---------------------------------------------------------------------------
# Parser (full AST construction)
# ---------------------------------------------------------------------------


def parse(text: str) -> Document:
    """Parse a Divinum Officium document string into a Document AST.

    Args:
        text: The full text content of a .txt file.

    Returns:
        A ``Document`` AST with preamble lines and sections.

    Raises:
        lark.exceptions.UnexpectedInput: If the document cannot be parsed.
    """
    tree = _parser.parse(text)
    transformer = DOTransformer()
    return transformer.transform(tree)


def parse_file(path: str | Path) -> Document:
    """Parse a Divinum Officium .txt file into a Document AST.

    Args:
        path: Path to the .txt file.

    Returns:
        A ``Document`` AST.
    """
    text = Path(path).read_text(encoding="utf-8-sig")
    return parse(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Parser functions
    "Tokenizer",
    "parse",
    "parse_file",
    # AST nodes
    "ChantRef",
    "ConditionalLine",
    "CongregationLine",
    "CrossRef",
    "DeaconLine",
    "DialogResponse",
    "DialogVersicle",
    "Document",
    "GloriaRef",
    "Heading",
    "Line",
    "LineKind",
    "MacroRef",
    "MinisterLine",
    "PriestLine",
    "RankValue",
    "Response",
    "RubricCondition",
    "RuleDirective",
    "ScriptureRef",
    "Section",
    "SectionHeader",
    "Separator",
    "ShortResponseBr",
    "SubroutineRef",
    "TextLine",
    "Versicle",
    "WaitDirective",
]
