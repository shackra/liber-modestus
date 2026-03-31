"""Tests for the scriptura module."""

import datetime

from scriptura import (
    Book,
    VerseId,
    book_name,
    lookup_book,
    parse_citation,
)
from scriptura.canon import (
    english_name,
    is_deuterocanonical,
    latin_abbr,
    latin_name,
)

# ---------------------------------------------------------------------------
# Canon: 73 books
# ---------------------------------------------------------------------------


class TestBookEnum:
    def test_73_books_defined(self):
        assert len(Book) == 73

    def test_genesis_is_1(self):
        assert Book.GENESIS == 1

    def test_revelation_is_66(self):
        assert Book.APOCALYPSIS == 66

    def test_deuterocanonical_books_67_to_73(self):
        assert Book.TOBIT == 67
        assert Book.JUDITH == 68
        assert Book.SAPIENTIA == 69
        assert Book.SIRACH == 70
        assert Book.BARUCH == 71
        assert Book.MACCABAEORUM_1 == 72
        assert Book.MACCABAEORUM_2 == 73

    def test_deuterocanonical_flag(self):
        for book in Book:
            expected = 67 <= book.value <= 73
            assert is_deuterocanonical(book) is expected, f"{book} flag mismatch"

    def test_latin_names_present(self):
        for book in Book:
            name = latin_name(book)
            assert name
            assert len(name) > 0

    def test_english_names_present(self):
        for book in Book:
            name = english_name(book)
            assert name
            assert len(name) > 0


class TestAbbreviationLookup:
    def test_latin_abbreviations(self):
        cases = [
            ("Gen", Book.GENESIS),
            ("Exod", Book.EXODUS),
            ("Lev", Book.LEVITICUS),
            ("Num", Book.NUMERI),
            ("Deut", Book.DEUTERONOMIUM),
            ("Ps", Book.PSALMI),
            ("Prov", Book.PROVERBIA),
            ("Eccl", Book.ECCLESIASTES),
            ("Isa", Book.ISAIAE),
            ("Jer", Book.JEREMIAE),
            ("Lam", Book.LAMENTATIONES),
            ("Ezek", Book.EZECHIELIS),
            ("Dan", Book.DANIELIS),
            ("Matt", Book.MATTHAEUS),
            ("Mc", Book.MARCUS),
            ("Lc", Book.LUCAS),
            ("Io", Book.JOANNES),
            ("Act", Book.ACTUS),
            ("Rom", Book.ROMANOS),
            ("Gal", Book.GALATAS),
            ("Eph", Book.Ephesus),
            ("Phil", Book.PHILIPPENSES),
            ("Col", Book.COLOSSENSES),
            ("Heb", Book.HEBRAEOS),
            ("Jac", Book.JACOBI),
            ("Jud", Book.JUDAE),
            ("Apoc", Book.APOCALYPSIS),
            # Deuterocanonical
            ("Tob", Book.TOBIT),
            ("Jdt", Book.JUDITH),
            ("Sap", Book.SAPIENTIA),
            ("Eccli", Book.SIRACH),
            ("Bar", Book.BARUCH),
            ("1Mach", Book.MACCABAEORUM_1),
            ("2Mach", Book.MACCABAEORUM_2),
            # Missal-specific Latin variants
            ("Joann", Book.JOANNES),
            ("Joanne", Book.JOANNES),
            ("Prov", Book.PROVERBIA),
            ("Os", Book.HOSEAE),
        ]
        for abbr, expected in cases:
            result = lookup_book(abbr)
            assert (
                result == expected
            ), f"lookup_book({abbr!r}) = {result}, expected {expected}"

    def test_osis_english_abbreviations(self):
        cases = [
            ("Gen", Book.GENESIS),
            ("Exod", Book.EXODUS),
            ("Ps", Book.PSALMI),
            ("Prov", Book.PROVERBIA),
            ("Matt", Book.MATTHAEUS),
            ("Mark", Book.MARCUS),
            ("Luke", Book.LUCAS),
            ("John", Book.JOANNES),
            ("Rev", Book.APOCALYPSIS),
            ("Rom", Book.ROMANOS),
            ("Gal", Book.GALATAS),
            ("Tob", Book.TOBIT),
            ("Judith", Book.JUDITH),
            ("Wisdom", Book.SAPIENTIA),
            ("Sirach", Book.SIRACH),
            ("Baruch", Book.BARUCH),
            ("1 Maccabees", Book.MACCABAEORUM_1),
            ("2 Maccabees", Book.MACCABAEORUM_2),
        ]
        for abbr, expected in cases:
            result = lookup_book(abbr)
            assert (
                result == expected
            ), f"lookup_book({abbr!r}) = {result}, expected {expected}"

    def test_case_insensitive(self):
        for abbr in ["Ps", "ps", "PS", "Ps", "JOANN", "joann", "JoAnn"]:
            result = lookup_book(abbr)
            assert result is not None, f"lookup_book({abbr!r}) returned None"

    def test_prefixed_books(self):
        cases = [
            ("1John", Book.JOANNIS_1),
            ("2John", Book.JOANNIS_2),
            ("3John", Book.JOANNIS_3),
            ("1Pet", Book.PETRI_1),
            ("2Pet", Book.PETRI_2),
            ("1Tim", Book.TIMOTHEUM_1),
            ("2Tim", Book.TIMOTHEUM_2),
            ("1Cor", Book.CORINTHIOS_1),
            ("2Cor", Book.CORINTHIOS_2),
            ("1Sam", Book.SAMUEL_1),
            ("2Sam", Book.SAMUEL_2),
            ("1Mach", Book.MACCABAEORUM_1),
            ("2Mach", Book.MACCABAEORUM_2),
        ]
        for abbr, expected in cases:
            result = lookup_book(abbr)
            assert (
                result == expected
            ), f"lookup_book({abbr!r}) = {result}, expected {expected}"

    def test_not_found_returns_none(self):
        assert lookup_book("XyzNotABook") is None
        assert lookup_book("") is None
        assert lookup_book("   ") is None


# ---------------------------------------------------------------------------
# VerseId: encoding / decoding
# ---------------------------------------------------------------------------


class TestVerseId:
    def test_encode_genesis_1_1(self):
        vid = VerseId(Book.GENESIS, 1, 1)
        assert vid.to_int() == 1_001_001

    def test_encode_joann_3_16(self):
        vid = VerseId(Book.JOANNES, 3, 16)
        assert vid.to_int() == 43_003_016

    def test_encode_tobit(self):
        vid = VerseId(Book.TOBIT, 5, 7)
        assert vid.to_int() == 67_005_007

    def test_roundtrip(self):
        cases = [
            (Book.GENESIS, 1, 1),
            (Book.PSALMI, 118, 164),
            (Book.JOANNES, 3, 16),
            (Book.APOCALYPSIS, 22, 21),
            (Book.TOBIT, 5, 7),
            (Book.SIRACH, 15, 3),
        ]
        for book, ch, v in cases:
            vid = VerseId(book, ch, v)
            decoded = VerseId.from_int(vid.to_int())
            assert decoded.book == book
            assert decoded.chapter == ch
            assert decoded.verse == v

    def test_int_conversion(self):
        vid = VerseId(Book.GENESIS, 1, 1)
        assert int(vid) == 1_001_001

    def test_sortable(self):
        v1 = VerseId(Book.GENESIS, 1, 1)
        v2 = VerseId(Book.GENESIS, 1, 2)
        v3 = VerseId(Book.GENESIS, 2, 1)
        v4 = VerseId(Book.JOANNES, 3, 16)
        assert v1 < v2 < v3 < v4

    def test_sql_value(self):
        vid = VerseId(Book.GENESIS, 1, 1)
        assert vid.to_sql_value() == vid.to_int()


# ---------------------------------------------------------------------------
# Parser: basic formats
# ---------------------------------------------------------------------------


class TestParserBasic:
    def test_simple_verse_range(self):
        ref = parse_citation("!Ps 24:1-3")
        assert ref is not None
        assert ref.book == Book.PSALMI
        assert ref.chapter == 24
        assert ref.verse_start == 1
        assert ref.verse_end == 3
        assert ref.is_chapter_ref is False
        assert len(ref.verse_ids) == 3
        assert ref.verse_ids == (19_024_001, 19_024_002, 19_024_003)

    def test_strips_leading_bang(self):
        ref = parse_citation("!Ps 24:1-3")
        assert ref is not None

    def test_strips_trailing_period(self):
        ref = parse_citation("!Ps 83:5.")
        assert ref is not None
        assert ref.verse_start == 5
        assert ref.verse_end == 5

    def test_single_verse(self):
        ref = parse_citation("!Ps 83:5")
        assert ref is not None
        assert ref.verse_start == 5
        assert ref.verse_end == 5
        assert len(ref.verse_ids) == 1


class TestParserCommaAsChapterSeparator:
    def test_comma_chapter_separator(self):
        ref = parse_citation("!Ps 24,1-3")
        assert ref is not None
        assert ref.book == Book.PSALMI
        assert ref.chapter == 24
        assert ref.verse_start == 1
        assert ref.verse_end == 3
        assert len(ref.verse_ids) == 3


class TestParserVerseChains:
    def test_verse_chain_joann(self):
        ref = parse_citation("!Joann 11:47-49, 50, 53")
        assert ref is not None
        assert ref.book == Book.JOANNES
        assert ref.chapter == 11
        assert ref.verse_start == 47
        assert ref.verse_end == 53
        assert len(ref.verse_ids) == 5

    def test_verse_chain_romans(self):
        ref = parse_citation("!Rom 1:2, 3, 5, 8; 9:2, 10")
        assert ref is not None
        assert ref.book == Book.ROMANOS
        assert ref.chapter == 1
        assert ref.verse_start == 2
        assert ref.verse_end == 8
        assert len(ref.verse_ids) == 6  # 1:2,3,5,8 + 9:2,10


class TestParserMultiSegment:
    def test_book_carry_forward_psalms(self):
        ref = parse_citation("!Ps 73:20; 73:19; 73:23")
        assert ref is not None
        assert ref.book == Book.PSALMI
        assert ref.chapter == 73
        assert len(ref.verse_ids) == 3

    def test_cross_chapter_exodus(self):
        ref = parse_citation("!Exod 15:27; 16:1-7")
        assert ref is not None
        assert ref.book == Book.EXODUS
        assert ref.chapter == 15
        assert len(ref.verse_ids) == 8  # 15:27 + 16:1-7

    def test_prov_chained(self):
        ref = parse_citation("!Prov 23:24; 23:25")
        assert ref is not None
        assert ref.book == Book.PROVERBIA
        assert ref.chapter == 23
        assert len(ref.verse_ids) == 2

    def test_peter_112_cross_ref(self):
        ref = parse_citation("!Matt 28:39, 41")
        assert ref is not None
        assert ref.book == Book.MATTHAEUS
        assert ref.chapter == 28
        assert len(ref.verse_ids) == 2


class TestParserSingleChapterBooks:
    def test_obad_single_verse(self):
        ref = parse_citation("!Obad 2")
        assert ref is not None
        assert ref.book == Book.ABDIAE
        assert ref.chapter == 1
        assert ref.verse_start == 2
        assert ref.verse_end == 2
        assert len(ref.verse_ids) == 1
        assert ref.is_chapter_ref is False

    def test_3john(self):
        ref = parse_citation("!3John 4")
        assert ref is not None
        assert ref.book == Book.JOANNIS_3
        assert ref.chapter == 1
        assert ref.verse_start == 4
        assert ref.verse_end == 4
        assert len(ref.verse_ids) == 1

    def test_jude(self):
        ref = parse_citation("!Jud 1")
        assert ref is not None
        assert ref.book == Book.JUDAE


class TestParserNonCitations:
    def test_rubric_returns_none(self):
        assert parse_citation("!Oratio propria.") is None
        assert parse_citation("!Antiphona") is None
        assert parse_citation("!Vel aliud") is None
        assert parse_citation("!Deinde Sacerdos stans") is None

    def test_display_marker_returns_none(self):
        assert parse_citation("!*S") is None
        assert parse_citation("!*nD") is None
        assert parse_citation("!*SnD") is None

    def test_empty_string_returns_none(self):
        assert parse_citation("") is None
        assert parse_citation("!") is None

    def test_unknown_book_returns_none(self):
        assert parse_citation("!XyzNotABook 1:1") is None


class TestParserDeuterocanonical:
    def test_tobit(self):
        ref = parse_citation("!Tob 5:7-9")
        assert ref is not None
        assert ref.book == Book.TOBIT
        assert ref.chapter == 5
        assert len(ref.verse_ids) == 3

    def test_judith(self):
        ref = parse_citation("!Jdt 10:1-5")
        assert ref is not None
        assert ref.book == Book.JUDITH
        assert ref.chapter == 10
        assert len(ref.verse_ids) == 5

    def test_wisdom(self):
        ref = parse_citation("!Sap 16:20")
        assert ref is not None
        assert ref.book == Book.SAPIENTIA

    def test_sirach(self):
        ref = parse_citation("!Eccli 15:3-6")
        assert ref is not None
        assert ref.book == Book.SIRACH
        assert ref.chapter == 15
        assert len(ref.verse_ids) == 4

    def test_apocalypse(self):
        ref = parse_citation("!Apoc 14:1-5")
        assert ref is not None
        assert ref.book == Book.APOCALYPSIS
        assert ref.chapter == 14
        assert len(ref.verse_ids) == 5


# ---------------------------------------------------------------------------
# Locales
# ---------------------------------------------------------------------------


class TestLocales:
    def test_latin_fallback(self):
        for book in Book:
            name = book_name(book, "la")
            assert name
            assert len(name) > 0

    def test_spanish_psalms(self):
        assert book_name(Book.PSALMI, "es") == "Salmos"

    def test_spanish_genesis(self):
        assert book_name(Book.GENESIS, "es") == "Génesis"

    def test_spanish_joann(self):
        assert book_name(Book.JOANNES, "es") == "Juan"

    def test_spanish_deuterocanonical(self):
        assert book_name(Book.TOBIT, "es") == "Tobías"
        assert book_name(Book.JUDITH, "es") == "Judit"
        assert book_name(Book.SAPIENTIA, "es") == "Sabiduría"
        assert book_name(Book.SIRACH, "es") == "Sirácida"

    def test_english_names(self):
        assert book_name(Book.GENESIS, "en") == "Genesis"
        assert book_name(Book.PSALMI, "en") == "Psalms"
        assert book_name(Book.JOANNES, "en") == "John"
        assert book_name(Book.APOCALYPSIS, "en") == "Revelation"

    def test_polish_psalms(self):
        assert book_name(Book.PSALMI, "pl") == "Księga Psalmów"

    def test_unknown_locale_falls_back_to_latin(self):
        result = book_name(Book.GENESIS, "xx")
        assert result == latin_name(Book.GENESIS)


# ---------------------------------------------------------------------------
# PostgreSQL readiness
# ---------------------------------------------------------------------------


class TestPostgresReadiness:
    def test_verse_ids_sortable(self):
        v1 = VerseId(Book.GENESIS, 1, 1)
        v2 = VerseId(Book.GENESIS, 1, 2)
        v3 = VerseId(Book.GENESIS, 2, 1)
        v4 = VerseId(Book.APOCALYPSIS, 22, 21)
        assert sorted([v4, v1, v3, v2]) == [v1, v2, v3, v4]

    def test_joann_3_range_query_bounds(self):
        """All verses in John 3 have IDs in [43_003_001, 43_003_999]."""
        vid_start = VerseId(Book.JOANNES, 3, 1).to_int()
        vid_end = VerseId(Book.JOANNES, 3, 999).to_int()
        assert vid_start == 43_003_001
        assert vid_end == 43_003_999
        # John 3:16 is in this range
        vid_jn316 = VerseId(Book.JOANNES, 3, 16).to_int()
        assert vid_start <= vid_jn316 <= vid_end

    def test_psalm_118_all_ids_contiguous(self):
        """All verse IDs for Psalm 118 are in [19_118_001, 19_118_XXX]."""
        vid_1 = VerseId(Book.PSALMI, 118, 1).to_int()
        assert vid_1 == 19_118_001
