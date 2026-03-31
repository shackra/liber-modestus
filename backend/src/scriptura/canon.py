"""Canonical book enumeration for the Catholic Bible (73 books).

Books 1-66 follow the Protestant canon order (Vulgate ordering).
Books 67-73 are the deuterocanonical books, appended after Revelation.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Book enumeration
# ---------------------------------------------------------------------------


class Book(enum.IntEnum):
    """The 73 books of the Catholic Bible, numbered 1-73.

    Books 1-66: Protestant canon (same order as the Vulgate).
    Books 67-73: Deuterocanonical books, appended after Revelation.

    The numbering is the canonical numbering used by the library for all
    internal computations (verse IDs, etc.).
    """

    GENESIS = 1
    EXODUS = 2
    LEVITICUS = 3
    NUMERI = 4
    DEUTERONOMIUM = 5
    JOSUE = 6
    JUDICES = 7
    RUTH = 8
    SAMUEL_1 = 9
    SAMUEL_2 = 10
    REGUM_1 = 11
    REGUM_2 = 12
    PARALIPOMENON_1 = 13
    PARALIPOMENON_2 = 14
    ESDRAE = 15
    NEEMIAS = 16
    ESTHER = 17
    JOB = 18
    PSALMI = 19
    PROVERBIA = 20
    ECCLESIASTES = 21
    CANTICUM_CANTICORUM = 22
    ISAIAE = 23
    JEREMIAE = 24
    LAMENTATIONES = 25
    EZECHIELIS = 26
    DANIELIS = 27
    HOSEAE = 28
    JOEL = 29
    AMOS = 30
    ABDIAE = 31
    JONAE = 32
    MICHAE = 33
    NAHUM = 34
    HABACUC = 35
    SOPHONIAE = 36
    AGGAEI = 37
    ZACHARIAE = 38
    MALACHIAE = 39
    MATTHAEUS = 40
    MARCUS = 41
    LUCAS = 42
    JOANNES = 43
    ACTUS = 44
    ROMANOS = 45
    CORINTHIOS_1 = 46
    CORINTHIOS_2 = 47
    GALATAS = 48
    Ephesus = 49
    PHILIPPENSES = 50
    COLOSSENSES = 51
    THESSALONICENSES_1 = 52
    THESSALONICENSES_2 = 53
    TIMOTHEUM_1 = 54
    TIMOTHEUM_2 = 55
    TITUM = 56
    PHILEMONEM = 57
    HEBRAEOS = 58
    JACOBI = 59
    PETRI_1 = 60
    PETRI_2 = 61
    JOANNIS_1 = 62
    JOANNIS_2 = 63
    JOANNIS_3 = 64
    JUDAE = 65
    APOCALYPSIS = 66
    TOBIT = 67
    JUDITH = 68
    SAPIENTIA = 69
    SIRACH = 70
    BARUCH = 71
    MACCABAEORUM_1 = 72
    MACCABAEORUM_2 = 73


# ---------------------------------------------------------------------------
# Book metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _BookMeta:
    latin_abbr: str
    latin_name: str
    english_name: str
    is_deuterocanonical: bool = False


_BOOK_META: dict[Book, _BookMeta] = {
    Book.GENESIS: _BookMeta("Gen", "Genesis", "Genesis"),
    Book.EXODUS: _BookMeta("Exod", "Exodus", "Exodus"),
    Book.LEVITICUS: _BookMeta("Lev", "Leviticus", "Leviticus"),
    Book.NUMERI: _BookMeta("Num", "Numeri", "Numbers"),
    Book.DEUTERONOMIUM: _BookMeta("Deut", "Deuteronomium", "Deuteronomy"),
    Book.JOSUE: _BookMeta("Jos", "Josue", "Joshua"),
    Book.JUDICES: _BookMeta("Jdgs", "Judices", "Judges"),
    Book.RUTH: _BookMeta("Ruth", "Ruth", "Ruth"),
    Book.SAMUEL_1: _BookMeta("1Sam", "I Samuel", "1 Samuel"),
    Book.SAMUEL_2: _BookMeta("2Sam", "II Samuel", "2 Samuel"),
    Book.REGUM_1: _BookMeta("1Reg", "III Regum", "1 Kings"),
    Book.REGUM_2: _BookMeta("2Reg", "IV Regum", "2 Kings"),
    Book.PARALIPOMENON_1: _BookMeta("1Par", "I Paralipomenon", "1 Chronicles"),
    Book.PARALIPOMENON_2: _BookMeta("2Par", "II Paralipomenon", "2 Chronicles"),
    Book.ESDRAE: _BookMeta("Esd", "Esdrae", "Ezra"),
    Book.NEEMIAS: _BookMeta("Neh", "Nehemias", "Nehemiah"),
    Book.ESTHER: _BookMeta("Est", "Esther", "Esther"),
    Book.JOB: _BookMeta("Job", "Job", "Job"),
    Book.PSALMI: _BookMeta("Ps", "Psalmi", "Psalms"),
    Book.PROVERBIA: _BookMeta("Prov", "Proverbia", "Proverbs"),
    Book.ECCLESIASTES: _BookMeta("Eccl", "Ecclesiastes", "Ecclesiastes"),
    Book.CANTICUM_CANTICORUM: _BookMeta("Cant", "Canticum Canticorum", "Song of Songs"),
    Book.ISAIAE: _BookMeta("Isa", "Isaias", "Isaiah"),
    Book.JEREMIAE: _BookMeta("Jer", "Jeremias", "Jeremiah"),
    Book.LAMENTATIONES: _BookMeta("Lam", "Lamentationes", "Lamentations"),
    Book.EZECHIELIS: _BookMeta("Ezek", "Ezechielis", "Ezekiel"),
    Book.DANIELIS: _BookMeta("Dan", "Daniel", "Daniel"),
    Book.HOSEAE: _BookMeta("Hos", "Osee", "Hosea"),
    Book.JOEL: _BookMeta("Joel", "Joel", "Joel"),
    Book.AMOS: _BookMeta("Am", "Amos", "Amos"),
    Book.ABDIAE: _BookMeta("Abd", "Abdias", "Obadiah"),
    Book.JONAE: _BookMeta("Jon", "Jonas", "Jonah"),
    Book.MICHAE: _BookMeta("Mich", "Michaeas", "Micah"),
    Book.NAHUM: _BookMeta("Nah", "Nahum", "Nahum"),
    Book.HABACUC: _BookMeta("Hab", "Abacuc", "Habakkuk"),
    Book.SOPHONIAE: _BookMeta("Sph", "Sophonias", "Zephaniah"),
    Book.AGGAEI: _BookMeta("Agg", "Aggaeus", "Haggai"),
    Book.ZACHARIAE: _BookMeta("Zach", "Zacharias", "Zechariah"),
    Book.MALACHIAE: _BookMeta("Mal", "Malachias", "Malachi"),
    Book.MATTHAEUS: _BookMeta("Matt", "Matthaeus", "Matthew"),
    Book.MARCUS: _BookMeta("Mc", "Marcus", "Mark"),
    Book.LUCAS: _BookMeta("Lc", "Lucas", "Luke"),
    Book.JOANNES: _BookMeta("Io", "Joannes", "John"),
    Book.ACTUS: _BookMeta("Act", "Actus", "Acts"),
    Book.ROMANOS: _BookMeta("Rom", "Romanos", "Romans"),
    Book.CORINTHIOS_1: _BookMeta("1Cor", "I Corinthios", "1 Corinthians"),
    Book.CORINTHIOS_2: _BookMeta("2Cor", "II Corinthios", "2 Corinthians"),
    Book.GALATAS: _BookMeta("Gal", "Galatas", "Galatians"),
    Book.Ephesus: _BookMeta("Eph", "Ephesios", "Ephesians"),
    Book.PHILIPPENSES: _BookMeta("Phil", "Philippenses", "Philippians"),
    Book.COLOSSENSES: _BookMeta("Col", "Colossenses", "Colossians"),
    Book.THESSALONICENSES_1: _BookMeta("1Th", "I Thessalonicenses", "1 Thessalonians"),
    Book.THESSALONICENSES_2: _BookMeta("2Th", "II Thessalonicenses", "2 Thessalonians"),
    Book.TIMOTHEUM_1: _BookMeta("1Tim", "I Timotheum", "1 Timothy"),
    Book.TIMOTHEUM_2: _BookMeta("2Tim", "II Timotheum", "2 Timothy"),
    Book.TITUM: _BookMeta("Tit", "Ad Titum", "Titus"),
    Book.PHILEMONEM: _BookMeta("Phlm", "Ad Philemonem", "Philemon"),
    Book.HEBRAEOS: _BookMeta("Heb", "Ad Hebraeos", "Hebrews"),
    Book.JACOBI: _BookMeta("Jac", "Jacobi", "James"),
    Book.PETRI_1: _BookMeta("1Pet", "I Petri", "1 Peter"),
    Book.PETRI_2: _BookMeta("2Pet", "II Petri", "2 Peter"),
    Book.JOANNIS_1: _BookMeta("1Io", "I Joannis", "1 John"),
    Book.JOANNIS_2: _BookMeta("2Io", "II Joannis", "2 John"),
    Book.JOANNIS_3: _BookMeta("3Io", "III Joannis", "3 John"),
    Book.JUDAE: _BookMeta("Jud", "Judae", "Jude"),
    Book.APOCALYPSIS: _BookMeta("Apoc", "Apocalypsis", "Revelation"),
    Book.TOBIT: _BookMeta("Tob", "Tobias", "Tobit", True),
    Book.JUDITH: _BookMeta("Jdt", "Judith", "Judith", True),
    Book.SAPIENTIA: _BookMeta("Sap", "Sapientia", "Wisdom", True),
    Book.SIRACH: _BookMeta("Eccli", "Ecclesiasticus", "Sirach", True),
    Book.BARUCH: _BookMeta("Bar", "Baruch", "Baruch", True),
    Book.MACCABAEORUM_1: _BookMeta("1Mach", "I Machabaeorum", "1 Maccabees", True),
    Book.MACCABAEORUM_2: _BookMeta("2Mach", "II Machabaeorum", "2 Maccabees", True),
}


def latin_abbr(book: Book) -> str:
    """Return the canonical Latin abbreviation for *book*."""
    return _BOOK_META[book].latin_abbr


def latin_name(book: Book) -> str:
    """Return the Latin name for *book*."""
    return _BOOK_META[book].latin_name


def english_name(book: Book) -> str:
    """Return the English name for *book*."""
    return _BOOK_META[book].english_name


def is_deuterocanonical(book: Book) -> bool:
    """Return True if *book* is a deuterocanonical book (67-73)."""
    return _BOOK_META[book].is_deuterocanonical


# ---------------------------------------------------------------------------
# Abbreviation lookup
# ---------------------------------------------------------------------------

# All known abbreviations mapped to Book values.  Keys are lower-case
# for case-insensitive lookup.  Every key maps to exactly one Book.
#
# The table is built by reflecting over _BOOK_META and adding common
# English abbreviations and Latin variants.

_ABBR_TO_BOOK: dict[str, Book] = {}

# Primary abbreviations from the metadata table.
for _book, _meta in _BOOK_META.items():
    _abbr = _meta.latin_abbr.lower()
    _ABBR_TO_BOOK[_abbr] = _book
    # Also store the latin_name lower-cased
    _ABBR_TO_BOOK[_meta.latin_name.lower()] = _book

# English abbreviations and common variants.
_ENGLISH_ABBR: dict[str, Book] = {
    # Old Testament
    "genesis": Book.GENESIS,
    "exodus": Book.EXODUS,
    "leviticus": Book.LEVITICUS,
    "numbers": Book.NUMERI,
    "deuteronomy": Book.DEUTERONOMIUM,
    "joshua": Book.JOSUE,
    "judges": Book.JUDICES,
    "ruth": Book.RUTH,
    "1 samuel": Book.SAMUEL_1,
    "2 samuel": Book.SAMUEL_2,
    "1samuel": Book.SAMUEL_1,
    "2samuel": Book.SAMUEL_2,
    "1sam": Book.SAMUEL_1,
    "2sam": Book.SAMUEL_2,
    "i samuel": Book.SAMUEL_1,
    "ii samuel": Book.SAMUEL_2,
    "1 kings": Book.REGUM_1,
    "2 kings": Book.REGUM_2,
    "1 chronicles": Book.PARALIPOMENON_1,
    "2 chronicles": Book.PARALIPOMENON_2,
    "ezra": Book.ESDRAE,
    "nehemiah": Book.NEEMIAS,
    "esther": Book.ESTHER,
    "job": Book.JOB,
    "psalms": Book.PSALMI,
    "psalm": Book.PSALMI,
    "proverbs": Book.PROVERBIA,
    "proverb": Book.PROVERBIA,
    "ecclesiastes": Book.ECCLESIASTES,
    "song of songs": Book.CANTICUM_CANTICORUM,
    "song of solomon": Book.CANTICUM_CANTICORUM,
    "canticle of canticles": Book.CANTICUM_CANTICORUM,
    "isaiah": Book.ISAIAE,
    "jeremiah": Book.JEREMIAE,
    "lamentations": Book.LAMENTATIONES,
    "ezekiel": Book.EZECHIELIS,
    "daniel": Book.DANIELIS,
    "hosea": Book.HOSEAE,
    "joel": Book.JOEL,
    "amos": Book.AMOS,
    "obadiah": Book.ABDIAE,
    "obad": Book.ABDIAE,
    "jonah": Book.JONAE,
    "micah": Book.MICHAE,
    "nahum": Book.NAHUM,
    "habakkuk": Book.HABACUC,
    "zephaniah": Book.SOPHONIAE,
    "haggai": Book.AGGAEI,
    "zechariah": Book.ZACHARIAE,
    "malachi": Book.MALACHIAE,
    # New Testament
    "matthew": Book.MATTHAEUS,
    "matt": Book.MATTHAEUS,
    "mark": Book.MARCUS,
    "luke": Book.LUCAS,
    "john": Book.JOANNES,
    "joann": Book.JOANNES,
    "joanne": Book.JOANNES,
    "acts": Book.ACTUS,
    "romans": Book.ROMANOS,
    "rom": Book.ROMANOS,
    "1 corinthians": Book.CORINTHIOS_1,
    "2 corinthians": Book.CORINTHIOS_2,
    "1 cor": Book.CORINTHIOS_1,
    "2 cor": Book.CORINTHIOS_2,
    "1cor": Book.CORINTHIOS_1,
    "2cor": Book.CORINTHIOS_2,
    "galatians": Book.GALATAS,
    "gal": Book.GALATAS,
    "ephesians": Book.Ephesus,
    "eph": Book.Ephesus,
    "philippians": Book.PHILIPPENSES,
    "phil": Book.PHILIPPENSES,
    "colossians": Book.COLOSSENSES,
    "col": Book.COLOSSENSES,
    "1 thessalonians": Book.THESSALONICENSES_1,
    "2 thessalonians": Book.THESSALONICENSES_2,
    "1 thess": Book.THESSALONICENSES_1,
    "2 thess": Book.THESSALONICENSES_2,
    "1 timothy": Book.TIMOTHEUM_1,
    "2 timothy": Book.TIMOTHEUM_2,
    "1 tim": Book.TIMOTHEUM_1,
    "2 tim": Book.TIMOTHEUM_2,
    "1tim": Book.TIMOTHEUM_1,
    "2tim": Book.TIMOTHEUM_2,
    "titus": Book.TITUM,
    "tit": Book.TITUM,
    "philemon": Book.PHILEMONEM,
    "phlm": Book.PHILEMONEM,
    "hebrews": Book.HEBRAEOS,
    "heb": Book.HEBRAEOS,
    "james": Book.JACOBI,
    "jac": Book.JACOBI,
    "1 peter": Book.PETRI_1,
    "2 peter": Book.PETRI_2,
    "1 pet": Book.PETRI_1,
    "2 pet": Book.PETRI_2,
    "1peter": Book.PETRI_1,
    "2peter": Book.PETRI_2,
    "1 john": Book.JOANNIS_1,
    "2 john": Book.JOANNIS_2,
    "3 john": Book.JOANNIS_3,
    "1john": Book.JOANNIS_1,
    "2john": Book.JOANNIS_2,
    "3john": Book.JOANNIS_3,
    "1 io": Book.JOANNIS_1,
    "2 io": Book.JOANNIS_2,
    "3 io": Book.JOANNIS_3,
    "jude": Book.JUDAE,
    "revelation": Book.APOCALYPSIS,
    "rev": Book.APOCALYPSIS,
    # Deuterocanonical
    "tobit": Book.TOBIT,
    "tob": Book.TOBIT,
    "judith": Book.JUDITH,
    "jdt": Book.JUDITH,
    "wisdom": Book.SAPIENTIA,
    "sap": Book.SAPIENTIA,
    "sirach": Book.SIRACH,
    "ecclesiasticus": Book.SIRACH,
    "eccli": Book.SIRACH,
    "baruch": Book.BARUCH,
    "bar": Book.BARUCH,
    "1 maccabees": Book.MACCABAEORUM_1,
    "2 maccabees": Book.MACCABAEORUM_2,
    "1 mach": Book.MACCABAEORUM_1,
    "2 mach": Book.MACCABAEORUM_2,
    "1maccabees": Book.MACCABAEORUM_1,
    "2maccabees": Book.MACCABAEORUM_2,
    # Vulgate-style Latin abbreviations seen in missal files
    "ioel": Book.JOEL,
    "abd": Book.ABDIAE,
    "jon": Book.JONAE,
    "sph": Book.SOPHONIAE,
    "agg": Book.AGGAEI,
    "zech": Book.ZACHARIAE,
    "mal": Book.MALACHIAE,
    "os": Book.HOSEAE,  # Hosea abbreviation in some editions
    "lam": Book.LAMENTATIONES,
    "eze": Book.EZECHIELIS,
    "dan": Book.DANIELIS,
    "est": Book.ESTHER,
    "esd": Book.ESDRAE,
    "neh": Book.NEEMIAS,
    "reg": Book.REGUM_1,  # ambiguous: prefer 1Reg in ambiguity
    "par": Book.PARALIPOMENON_1,
    "philem": Book.PHILEMONEM,
}
for _k, _v in _ENGLISH_ABBR.items():
    _ABBR_TO_BOOK[_k.lower()] = _v

# Numered-book abbreviations (e.g. "3John" → 3 John)
for _book in (Book.JOANNIS_1, Book.JOANNIS_2, Book.JOANNIS_3):
    _meta = _BOOK_META[_book]
    _ABBR_TO_BOOK[_meta.latin_abbr.lower()] = _book

for _book in (
    Book.SAMUEL_1,
    Book.SAMUEL_2,
    Book.REGUM_1,
    Book.REGUM_2,
    Book.PARALIPOMENON_1,
    Book.PARALIPOMENON_2,
    Book.CORINTHIOS_1,
    Book.CORINTHIOS_2,
    Book.THESSALONICENSES_1,
    Book.THESSALONICENSES_2,
    Book.TIMOTHEUM_1,
    Book.TIMOTHEUM_2,
    Book.PETRI_1,
    Book.PETRI_2,
    Book.MACCABAEORUM_1,
    Book.MACCABAEORUM_2,
):
    _meta = _BOOK_META[_book]
    _ABBR_TO_BOOK[_meta.latin_abbr.lower()] = _book


def lookup_book(abbr: str) -> Book | None:
    """Return the Book corresponding to *abbr*, or None if not found.

    Lookup is case-insensitive.  Accepts Latin abbreviations, full Latin
    names, English names, and OSIS-style abbreviations.
    """
    return _ABBR_TO_BOOK.get(abbr.strip().lower())
