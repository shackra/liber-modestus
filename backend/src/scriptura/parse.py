"""Citation parser for missal scripture references.

This module parses Bible citation strings found in the missal text files
(e.g. ``!Ps 24:1-3``) into structured :class:`NormalizedReference`
objects.

Supported formats
----------------
- Simple range:      ``Ps 24:1-3``
- Verse chains:      ``Joann 11:47-49, 50, 53``
- Book carry-fwd:   ``Ps 73:20; 73:19; 73:23``
- Cross-chapter:    ``Exod 15:27; 16:1-7``
- Roman numerals:   ``Rom 1:2, 3, 5, 8; 9:2, 10``
- Chapter refs:     ``Gen 1, 3-4; 8, 9-10``
- Comma sep:        ``Ps 24,1-3``
- Single-chapter:   ``Obad 2`` (verse only)
- Prefixed books:   ``3John 4``
- Leading ``!``:    ``!Ps 24:1-3``
- Trailing ``.``:   ``Ps 83:5.``

Lines that are not recognizable Bible citations (e.g. rubrical
instructions) return ``None``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .canon import Book, lookup_book
from .types import NormalizedReference

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches a number that might be preceded by a prefix (e.g. "3John" → group 1="3", group 2="John")
_RE_PREFIXED_BOOK = re.compile(
    r"^(?P<prefix>\d+)?(?P<abbr>\D+)",
    re.IGNORECASE,
)

# Matches a chapter number optionally followed by verse spec.
# The separator between chapter and verses can be ':' or ','.
# Examples:
#   "24"           → chapter ref
#   "24:1-3"      → range
#   "24:1,2,3"    → chain
#   "24:1-3,5,7"  → range + chain
#   "24,1-3"      → comma sep
_RE_CHAPTER_VERSE = re.compile(
    r"^(?P<chapter>\d+)" r"(?:[:.,](?P<verses>[^;]+))?",
    re.IGNORECASE,
)

# Matches a verse or verse range within a chapter.
# Examples: "1", "1-3", "1,2,3", "1-3,5,7-9"
_RE_VERSE_SPEC = re.compile(
    r"(?P<start>\d+)(?:-(?P<end>\d+))?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helper: expand a verse spec into individual verse numbers
# ---------------------------------------------------------------------------


def _is_chapter_only_ref(text: str) -> bool:
    """Return True if *text* looks like a chapter-only reference.

    A chapter-only reference lists multiple chapters separated by commas.
    Each part is either a plain number or a chapter range (e.g. "3-4").
    If any part (other than the first) contains a dash, it is a verse
    reference (e.g. "24,1-3" → chapter 24, verses 1-3).

    Chapter-only:   "1, 3-4, 8, 9-10" (plain numbers or chapter ranges)
    Comma-chap-sep: "24,1-3" (dash in second part → verse ref)
    Verse chains:   "47-49, 50, 53" (colon present, skip)
    """
    text = text.strip()
    if not text:
        return False
    if ":" in text:
        return False
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) < 2:
        return False
    first_is_number = parts[0].isdigit()
    for part in parts:
        if part.isdigit():
            continue
        if re.match(r"^\d+-\d+$", part):
            continue
        return False
    if first_is_number and any("-" in p for p in parts[1:]):
        return False
    return True


def _expand_chapters(text: str) -> list[int]:
    """Expand a chapter spec like '1, 3-4, 8, 9-10' into a list of chapters."""
    chapters: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            parts = part.split("-", 1)
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                chapters.extend(range(int(parts[0]), int(parts[1]) + 1))
        elif part.isdigit():
            chapters.append(int(part))
    return chapters


def _expand_verses(verse_spec: str) -> list[int]:
    """Expand a verse spec like '1-3,5,7-9' into a list of integers."""
    verses: list[int] = []
    for part in verse_spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = _RE_VERSE_SPEC.match(part)
        if m:
            start = int(m.group("start"))
            end_str = m.group("end")
            if end_str:
                verses.extend(range(start, int(end_str) + 1))
            else:
                verses.append(start)
    return verses


# ---------------------------------------------------------------------------
# Helper: parse a chapter-verse portion
# ---------------------------------------------------------------------------


def _parse_chapter_verse(
    text: str,
    base_chapter: int | None = None,
) -> tuple[int, list[int]] | None:
    """Parse '24:1-3' or '24' into (chapter, [verse_numbers]).

    If *base_chapter* is given, it overrides the extracted chapter number.
    This is used when the chapter is already known (e.g. from a carry-forward
    token like '9:2,10' where the chapter=9 comes from the token itself).

    Returns ``None`` if the text cannot be parsed.
    """
    text = text.strip()
    if not text:
        return None

    m = _RE_CHAPTER_VERSE.match(text)
    if not m:
        return None

    chapter = int(m.group("chapter"))
    verse_spec = m.group("verses")

    if base_chapter is not None:
        chapter = base_chapter

    if not verse_spec:
        return chapter, []

    verses = _expand_verses(verse_spec)
    return chapter, verses


# ---------------------------------------------------------------------------
# Helper: extract book from a token
# ---------------------------------------------------------------------------


def _resolve_book(token: str) -> Book | None:
    """Resolve a token (possibly prefixed like '3John') to a Book.

    Handles:
    - Normal abbreviations: "Ps", "Prov", "Joann"
    - Prefixed books: "3John" (prefix → book number), "1Cor"
    - Full names: "Psalmi", "Genesis"
    """
    token = token.strip()

    # Try as-is first
    book = lookup_book(token)
    if book is not None:
        return book

    # Try prefixed form: "3John" → prefix="3", abbr="John"
    m = _RE_PREFIXED_BOOK.match(token)
    if m:
        prefix = m.group("prefix") or ""
        abbr = m.group("abbr")

        # Rebuild with space: "3 John" or just "John" if no prefix
        spaced = f"{prefix} {abbr}".strip()
        book = lookup_book(spaced)
        if book is not None:
            return book

        # Try the unprefixed form (just the abbreviation)
        book = lookup_book(abbr)
        if book is not None:
            return book

    return None


# ---------------------------------------------------------------------------
# Main parser entry point
# ---------------------------------------------------------------------------


def parse_citation(raw: str) -> NormalizedReference | None:
    """Parse a missal citation string into a NormalizedReference.

    Parameters
    ----------
    raw:
        The input string, e.g. ``"!Ps 24:1-3"`` or ``"Oratio propria."``.
        Leading ``!`` and trailing ``.`` are stripped automatically.

    Returns
    -------
    NormalizedReference
        If the string can be parsed as a Bible citation.
    None
        If the string is not recognisable as a Bible citation (e.g.
        rubrical instructions like ``"Oratio propria."``).

    Examples
    --------
    >>> ref = parse_citation("!Ps 24:1-3")
    >>> ref.book
    <Book.PSALMI: 19>
    >>> ref.verse_ids
    (19024001, 19024002, 19024003)

    >>> parse_citation("!Oratio propria.")
    None
    """
    text = raw.strip()

    # Strip leading !
    if text.startswith("!"):
        text = text[1:].strip()

    # Strip trailing period
    if text.endswith("."):
        text = text[:-1].strip()

    if not text:
        return None

    # Split on semicolons — each segment is a separate range
    segments = text.split(";")

    first_book: Book | None = None
    first_chapter = 0
    first_verse_start = 0
    first_verse_end = 0
    first_is_chapter_ref = False
    all_verse_ids: list[int] = []

    prev_book: Book | None = None

    for idx, segment in enumerate(segments):
        segment = segment.strip()
        if not segment:
            continue

        # Split on whitespace, but the first token might be "digit(s):verse" or
        # "digit(s):verse,digit" (e.g. "9:2,").  Re-join trailing fragments.
        parts = segment.split()
        if not parts:
            continue

        raw_first = parts[0]
        raw_rest = ", ".join(p.rstrip(",") for p in parts[1:]) if len(parts) > 1 else ""

        first_token: str
        raw_remainder: str

        if raw_first[0].isdigit():
            if ":" in raw_first:
                if raw_rest:
                    merged = f"{raw_first.rstrip(',')},{raw_rest}"
                    first_token = merged
                else:
                    first_token = raw_first
                raw_remainder = ""
            else:
                first_token = raw_first
                raw_remainder = raw_rest
        else:
            first_token = raw_first
            raw_remainder = raw_rest

        # Resolve the book from the first token.
        book = _resolve_book(first_token)

        if book is None:
            if prev_book is not None and first_token[0].isdigit():
                chapter_match = re.match(r"^(\d+)(?::.+)?$", first_token)
                if chapter_match:
                    chapter_num = int(chapter_match.group(1))
                    after_chapter = first_token[len(chapter_match.group(1)) :]
                    remainder = ""
                    if after_chapter.startswith(":") and raw_remainder:
                        remainder = after_chapter[1:] + "," + raw_remainder
                    elif after_chapter.startswith(":"):
                        remainder = after_chapter[1:]
                    elif raw_remainder:
                        remainder = raw_remainder
                    else:
                        remainder = ""
                    book = prev_book
                    chapter = chapter_num
                    verses: list[int] = []
                    if remainder:
                        if _is_chapter_only_ref(remainder):
                            if " " in remainder:
                                chapters = _expand_chapters(remainder)
                                chapter = chapters[0] if chapters else chapter
                            else:
                                verses = _expand_verses(remainder)
                        else:
                            verses = _expand_verses(remainder)
                    is_chapter_ref = not verses
                    if idx == 0:
                        first_book = book
                        first_chapter = chapter
                        first_verse_start = verses[0] if verses else 0
                        first_verse_end = verses[-1] if verses else 0
                        first_is_chapter_ref = is_chapter_ref
                    if verses and not is_chapter_ref:
                        for v in verses:
                            vid = book.value * 1_000_000 + chapter * 1_000 + v
                            all_verse_ids.append(vid)
                    prev_book = book
                    continue
                else:
                    return None
            else:
                return None

        if first_book is None:
            first_book = book

        prev_book = book

        if raw_remainder:
            if _is_chapter_only_ref(raw_remainder):
                chapters = _expand_chapters(raw_remainder)
                if not chapters:
                    return None
                chapter = chapters[0]
                verses = []
            else:
                result = _parse_chapter_verse(raw_remainder)
                if result is None:
                    return None
                chapter, verses = result
                if not verses and chapter > 1 and raw_remainder.strip().isdigit():
                    verses = [chapter]
                    chapter = 1
        else:
            chapter = 1
            verses = []

        is_chapter_ref = not verses

        if is_chapter_ref and first_token:
            parsed = _parse_chapter_verse(first_token)
            if parsed is not None and parsed[0] != 0:
                chapter = 1
                verses = [parsed[0]]
                is_chapter_ref = False

        if idx == 0:
            if verses:
                first_verse_start = verses[0]
                first_verse_end = verses[-1]
                first_is_chapter_ref = False
                first_chapter = chapter
            else:
                first_is_chapter_ref = True
                first_chapter = chapter
                first_verse_start = 0
                first_verse_end = 0

        if verses and not is_chapter_ref:
            for v in verses:
                vid = book.value * 1_000_000 + chapter * 1_000 + v
                all_verse_ids.append(vid)

    if first_book is None:
        return None

    return NormalizedReference(
        raw=raw,
        book=first_book,
        chapter=first_chapter,
        verse_start=first_verse_start,
        verse_end=first_verse_end,
        is_chapter_ref=first_is_chapter_ref,
        verse_ids=tuple(all_verse_ids),
    )
