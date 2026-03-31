"""Scriptura -- Bible citation parser and verse ID system.

This package provides:

- :class:`.canon.Book` -- the 73-book Catholic Bible enumeration.
- :func:`.parse.parse_citation` -- parse missal citation strings.
- :class:`.types.VerseId` -- individual verse identifiers.
- :class:`.types.NormalizedReference` -- fully parsed scripture references.
- :func:`.locales.book_name` -- localised book names.
- :mod:`.osis_to_sql` -- CLI tool to convert OSIS XML to SQL.
"""

from .canon import Book, english_name, latin_abbr, latin_name, lookup_book
from .locales import book_name
from .parse import parse_citation
from .types import NormalizedReference, VerseId

__all__ = [
    "Book",
    "VerseId",
    "NormalizedReference",
    "parse_citation",
    "lookup_book",
    "latin_abbr",
    "latin_name",
    "english_name",
    "book_name",
]
