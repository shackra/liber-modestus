"""Core data types for scriptura."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canon import Book


@dataclass(frozen=True)
class VerseId:
    """A single verse identified by book, chapter, and verse number.

    Internally stored as an integer (see *verse_id*) for efficient
    PostgreSQL storage and comparison.

    Verse ID encoding
    -----------------
    The verse ID is computed as::

        verse_id = book_id * 1_000_000 + chapter * 1_000 + verse

    This encoding ensures:
    - All verses in the same chapter are contiguous.
    - All verses in the same book are contiguous.
    - Natural ordering (Genesis 1:1 < Genesis 1:2 < ... < Revelation 22:21).

    Examples
    --------
    >>> vid = VerseId(Book.GENESIS, 1, 1)
    >>> vid.to_int()
    1001001
    >>> VerseId.from_int(43003016).to_int()
    43003016
    >>> VerseId.from_int(43003016).book
    <Book.JOANNES: 43>
    """

    book: Book
    chapter: int
    verse: int
    _int: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        vid = self.book.value * 1_000_000 + self.chapter * 1_000 + self.verse
        object.__setattr__(self, "_int", vid)

    def to_int(self) -> int:
        """Return the integer verse ID."""
        return self._int

    def to_sql_value(self) -> int:
        """Alias for :meth:`to_int`."""
        return self._int

    @classmethod
    def from_int(cls, vid: int) -> VerseId:
        """Reconstruct a VerseId from an integer verse ID."""
        book_id = vid // 1_000_000
        chapter = (vid % 1_000_000) // 1_000
        verse = vid % 1_000
        return cls(Book(book_id), chapter, verse)

    def __int__(self) -> int:
        return self._int

    def __lt__(self, other: VerseId) -> bool:
        return self._int < other._int


@dataclass(frozen=True)
class NormalizedReference:
    """A fully parsed and normalized scripture reference.

    Attributes
    ----------
    raw : str
        The original input string, e.g. ``"Ps 24:1-3"``.
    book : Book
        The canonical book enum value.
    chapter : int
        The chapter number.  May be 0 for chapter-only references.
    verse_start : int
        The starting verse number, or 0 for chapter-only references.
    verse_end : int
        The ending verse number, or 0 for chapter-only references.
        Equal to ``verse_start`` for single verses.
    is_chapter_ref : bool
        True when no verse numbers were given (e.g. ``"Gen 1, 3-4"``).
    verse_ids : tuple[int, ...]
        Expanded tuple of individual verse IDs for verse references.
        Empty for chapter-only references.

    Examples
    --------
    >>> ref = NormalizedReference("Ps 24:1-3", Book.PSALMI, 24, 1, 3, False, (19024001, 19024002, 19024003))
    >>> ref.book
    <Book.PSALMI: 19>
    >>> ref.verse_ids
    (19024001, 19024002, 19024003)
    """

    raw: str
    book: Book
    chapter: int
    verse_start: int
    verse_end: int
    is_chapter_ref: bool
    verse_ids: tuple[int, ...] = field(default_factory=tuple)
