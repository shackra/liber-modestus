#!/usr/bin/env python3
"""CLI tool to convert OSIS Bible XML files to PostgreSQL INSERT statements.

Usage::

    python -m scriptura.osis_to_sql --osis vulgata.xml --books osis.toml

The ``--books`` argument points to a TOML file mapping OSIS book IDs
(e.g. ``"Gen"``, ``"Ps"``, ``"John"``) to canonical Book enum values
(1-73).  See the example in ``osis_books.toml.example``.

Output is written to stdout by default, or to the path given by ``--output``.

Example ``osis_books.toml``::

    [books]
    "Gen" = 1      # Genesis
    "Exod" = 2     # Exodus
    ...
    "Ps" = 19      # Psalms
    "John" = 43    # John

The script generates ``INSERT INTO verses`` statements for PostgreSQL.
Run the output with ``psql``::

    psql -h localhost -U user mydb -f verses.sql
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from .canon import Book

# ---------------------------------------------------------------------------
# XML namespace
# ---------------------------------------------------------------------------

NS = {"osis": "http://www.bibletechnologies.net/2003/OSIS/namespace"}

# ---------------------------------------------------------------------------
# Toml loading (stdlib-based)
# ---------------------------------------------------------------------------


def _load_toml(path: Path) -> dict:
    """Load a TOML file using the stdlib tomllib (Python 3.11+)."""
    import tomllib

    with path.open("rb") as fh:
        return tomllib.load(fh)


# ---------------------------------------------------------------------------
# Verse extraction
# ---------------------------------------------------------------------------


def _osis_verse_id(book_id: int, chapter: int, verse: int) -> int:
    """Compute the canonical verse ID from book, chapter, and verse."""
    return book_id * 1_000_000 + chapter * 1_000 + verse


def _escape_sql(text: str) -> str:
    """Escape a string for safe SQL INSERT."""
    return text.replace("'", "''")


def _osis_to_sql(
    osis_path: Path,
    books_toml: Path,
    output_path: Path | None,
) -> None:
    """Convert an OSIS XML file to SQL INSERT statements."""
    books_map = _load_toml(books_toml)
    book_ids: dict[str, int] = books_map.get("books", {})

    tree = ET.parse(osis_path)
    root = tree.getroot()

    statements: list[str] = []
    statements.append(
        "-- OSIS to SQL conversion\n"
        f"-- Source: {osis_path}\n"
        f"-- Books mapping: {books_toml}\n"
        "-- Run with: psql -h HOST -U USER DBNAME -f verses.sql\n\n"
    )

    verse_count = 0

    # Iterate over all <verse> elements
    for verse_el in root.iter(
        "{http://www.bibletechnologies.net/2003/OSIS/namespace}verse"
    ):
        osis_id = verse_el.get("osisID", "")
        if not osis_id:
            continue

        # osisID format: "John.3.16" or "John.3.16-ESV" etc.
        # Split off any trailing translation marker
        osis_id_core = osis_id.split("-")[0]
        parts = osis_id_core.split(".")

        if len(parts) < 3:
            # Not a verse-level element
            continue

        osis_book = parts[0]
        try:
            chapter = int(parts[1])
            verse_num = int(parts[2])
        except ValueError:
            continue

        book_id = book_ids.get(osis_book)
        if book_id is None:
            print(
                f"WARNING: unknown OSIS book '{osis_book}' in verse {osis_id}, skipping",
                file=sys.stderr,
            )
            continue

        # Validate book ID is in range
        try:
            Book(book_id)
        except ValueError:
            print(
                f"WARNING: canonical book ID {book_id} for '{osis_book}' "
                f"is out of range, skipping {osis_id}",
                file=sys.stderr,
            )
            continue

        vid = _osis_verse_id(book_id, chapter, verse_num)

        # Get verse text — may be in the text content of the verse element
        # or in child <w> (word) elements
        text_parts: list[str] = []
        if verse_el.text:
            text_parts.append(verse_el.text)
        for child in verse_el:
            if child.text:
                text_parts.append(child.text)
            if child.tail:
                text_parts.append(child.tail)

        text = "".join(text_parts).strip()

        stmt = (
            f"INSERT INTO verses (verse_id, book_id, chapter, verse, text) "
            f"VALUES ({vid}, {book_id}, {chapter}, {verse_num}, "
            f"'{_escape_sql(text)}');"
        )
        statements.append(stmt)
        verse_count += 1

    output = "\n".join(statements) + "\n"

    if output_path:
        output_path.write_text(output)
        print(f"Wrote {verse_count} verse inserts to {output_path}", file=sys.stderr)
    else:
        sys.stdout.write(output)
        print(f"Generated {verse_count} verse inserts", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert OSIS Bible XML to PostgreSQL INSERT statements.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--osis",
        type=Path,
        required=True,
        help="Path to the OSIS XML file.",
    )
    parser.add_argument(
        "--books",
        type=Path,
        required=True,
        help=(
            "Path to a TOML file mapping OSIS book IDs to canonical "
            "Book enum values (1-73).  See osis_books.toml.example."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output .sql file path.  If omitted, writes to stdout.",
    )
    args = parser.parse_args(argv)

    if not args.osis.exists():
        print(f"ERROR: OSIS file not found: {args.osis}", file=sys.stderr)
        return 1

    if not args.books.exists():
        print(f"ERROR: Books TOML not found: {args.books}", file=sys.stderr)
        return 1

    try:
        _osis_to_sql(args.osis, args.books, args.output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
