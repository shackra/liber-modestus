"""Comprehensive tests for the Divinum Officium document parser.

Tests the full parse pipeline: lexer -> LALR(1) parser -> transformer -> AST.
"""

import os
from pathlib import Path

import pytest

from captator.parser import (
    CrossRef,
    Document,
    GloriaRef,
    Heading,
    LineKind,
    MacroRef,
    RankValue,
    RubricCondition,
    RuleDirective,
    ScriptureRef,
    Section,
    SectionHeader,
    Separator,
    SubroutineRef,
    TextLine,
    Versicle,
    parse,
    parse_file,
)
from captator.parser.ast_nodes import (
    ConditionalLine,
    DialogResponse,
    DialogVersicle,
    MinisterLine,
    PriestLine,
    WaitDirective,
)

# ---------------------------------------------------------------------------
# Path to test data
# ---------------------------------------------------------------------------

_DO_BASE = Path(__file__).parent.parent / "src" / "divinum-officium" / "web" / "www"
_MISSA_LATIN = _DO_BASE / "missa" / "Latin"

# Check if test data is available (submodule may not be cloned)
_HAS_DATA = _MISSA_LATIN.is_dir() and any(_MISSA_LATIN.glob("Sancti/*.txt"))


# ---------------------------------------------------------------------------
# Unit tests: parse() with inline strings
# ---------------------------------------------------------------------------


class TestParseBasic:
    """Test basic parsing of inline document strings."""

    def test_empty_document(self):
        doc = parse("")
        assert isinstance(doc, Document)
        assert doc.preamble == []
        assert doc.sections == []

    def test_single_section(self):
        doc = parse("[Rank]\nIn Epiphania Domini;;Duplex I classis;;7\n")
        assert len(doc.sections) == 1
        assert doc.sections[0].header.name == "Rank"
        assert len(doc.sections[0].body) == 1

    def test_multiple_sections(self):
        text = "[Rank]\nTest;;Duplex;;3\n\n[Rule]\nGloria\n\n[Oratio]\nDeus...\n"
        doc = parse(text)
        assert len(doc.sections) == 3
        assert doc.get_section_names() == ["Rank", "Rule", "Oratio"]

    def test_preamble_lines(self):
        text = "&Vidiaquam\n# Incipit\n[Rank]\nTest;;Duplex;;3\n"
        doc = parse(text)
        assert len(doc.preamble) == 2
        assert isinstance(doc.preamble[0], SubroutineRef)
        assert isinstance(doc.preamble[1], Heading)
        assert len(doc.sections) == 1

    def test_preamble_only(self):
        text = "# Heading\n&introitus\n!Rubric\n"
        doc = parse(text)
        assert len(doc.preamble) == 3
        assert doc.sections == []


class TestParseSectionHeaders:
    """Test section header parsing."""

    def test_simple_header(self):
        doc = parse("[Introitus]\nText\n")
        assert doc.sections[0].header.name == "Introitus"
        assert doc.sections[0].header.rubric is None

    def test_header_with_rubric(self):
        doc = parse("[Commemoratio Oratio] (rubrica tridentina)\nText\n")
        header = doc.sections[0].header
        assert header.name == "Commemoratio Oratio"
        assert header.rubric is not None
        assert header.rubric.expression == "rubrica tridentina"

    def test_header_with_complex_rubric(self):
        doc = parse("[Rank] (rubrica 196 aut rubrica 1955)\n;;Feria;;1.2\n")
        header = doc.sections[0].header
        assert header.rubric.expression == "rubrica 196 aut rubrica 1955"

    def test_duplicate_section_names(self):
        text = "[Rank]\nA;;B;;1\n\n" "[Rank] (rubrica 1960)\nC;;D;;2\n"
        doc = parse(text)
        ranks = doc.get_sections("Rank")
        assert len(ranks) == 2
        assert ranks[0].header.rubric is None
        assert ranks[1].header.rubric.expression == "rubrica 1960"


class TestParseCrossRef:
    """Test cross-reference line parsing."""

    def test_simple_file_ref(self):
        doc = parse("[X]\n@Tempora/Nat2-0\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, CrossRef)
        assert line.file_ref == "Tempora/Nat2-0"
        assert line.section_ref is None
        assert line.substitutions is None

    def test_file_and_section_ref(self):
        doc = parse("[X]\n@Sancti/08-03:Oratio\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, CrossRef)
        assert line.file_ref == "Sancti/08-03"
        assert line.section_ref == "Oratio"

    def test_file_section_and_substitution(self):
        doc = parse("[X]\n@Commune/C1:Oratio:s/N\\./Petri/g\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, CrossRef)
        assert line.file_ref == "Commune/C1"
        assert line.section_ref == "Oratio"
        assert line.substitutions == "s/N\\./Petri/g"

    def test_self_reference(self):
        doc = parse("[X]\n@:Ant Vespera\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, CrossRef)
        assert line.is_self_ref
        assert line.section_ref == "Ant Vespera"

    def test_commune_ref(self):
        doc = parse("[X]\n@Commune/C2a\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, CrossRef)
        assert line.file_ref == "Commune/C2a"


class TestParseMacroRef:
    """Test macro reference parsing."""

    def test_per_dominum(self):
        doc = parse("[X]\n$Per Dominum\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, MacroRef)
        assert line.macro_name == "Per Dominum"

    def test_qui_tecum(self):
        doc = parse("[X]\n$Qui tecum\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, MacroRef)
        assert line.macro_name == "Qui tecum"

    def test_qui_vivis(self):
        doc = parse("[X]\n$Qui vivis\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, MacroRef)
        assert line.macro_name == "Qui vivis"


class TestParseSubroutineRef:
    """Test subroutine reference parsing."""

    def test_simple_subroutine(self):
        doc = parse("[X]\n&introitus\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, SubroutineRef)
        assert line.function_name == "introitus"
        assert line.arguments is None

    def test_subroutine_with_args(self):
        doc = parse("[X]\n&psalm(94)\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, SubroutineRef)
        assert line.function_name == "psalm"
        assert line.arguments == "94"

    def test_gloria_ref(self):
        doc = parse("[X]\n&Gloria\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, GloriaRef)


class TestParseRankValue:
    """Test rank value line parsing."""

    def test_full_rank(self):
        doc = parse("[Rank]\nIn Epiphania Domini;;Duplex I classis;;7\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, RankValue)
        assert line.display_name == "In Epiphania Domini"
        assert line.rank_class == "Duplex I classis"
        assert line.weight == "7"
        assert line.common_ref is None

    def test_rank_with_common(self):
        doc = parse(
            "[Rank]\nSecunda die infra Octavam;;Semiduplex;;5.6;;ex Sancti/01-06\n"
        )
        line = doc.sections[0].body[0]
        assert isinstance(line, RankValue)
        assert line.display_name == "Secunda die infra Octavam"
        assert line.rank_class == "Semiduplex"
        assert line.weight == "5.6"
        assert line.common_ref == "ex Sancti/01-06"

    def test_rank_empty_name(self):
        doc = parse("[Rank]\n;;Duplex I classis;;6.1;;\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, RankValue)
        assert line.display_name == ""
        assert line.rank_class == "Duplex I classis"
        assert line.weight == "6.1"

    def test_rank_with_conditional(self):
        text = "[Rank]\n;;Duplex;;5;;ex C3\n(sed rubrica 196)\n;;Duplex;;5;;ex C3\n"
        doc = parse(text)
        body = doc.sections[0].body
        assert len(body) == 3
        assert isinstance(body[0], RankValue)
        assert isinstance(body[1], ConditionalLine)
        assert body[1].condition.expression == "sed rubrica 196"
        assert isinstance(body[2], RankValue)


class TestParseRuleDirective:
    """Test rule directive parsing."""

    def test_simple_keyword(self):
        doc = parse("[Rule]\nGloria\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, RuleDirective)
        assert line.keyword == "Gloria"
        assert line.value is None

    def test_key_value(self):
        doc = parse("[Rule]\nPrefatio=Epi\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, RuleDirective)
        assert line.keyword == "Prefatio"
        assert line.value == "Epi"

    def test_ex_directive(self):
        doc = parse("[Rule]\nex Sancti/12-25m3;\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, RuleDirective)
        assert line.keyword == "ex Sancti/12-25m3"

    def test_complex_suffragium(self):
        doc = parse("[Rule]\nSuffragium=Maria2;Papa;Ecclesia;;\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, RuleDirective)
        assert line.keyword == "Suffragium"
        assert line.value == "Maria2;Papa;Ecclesia;;"


class TestParseScriptureRef:
    """Test scripture reference and rubric instruction parsing."""

    def test_psalm_citation(self):
        doc = parse("[X]\n!Ps 24:1-3\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, ScriptureRef)
        assert line.body == "Ps 24:1-3"
        assert not line.is_display_marker

    def test_display_marker(self):
        doc = parse("[X]\n!*S\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, ScriptureRef)
        assert line.is_display_marker
        assert line.display_marker == "S"

    def test_display_marker_nd(self):
        doc = parse("[X]\n!*nD\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, ScriptureRef)
        assert line.is_display_marker
        assert line.display_marker == "nD"


class TestParseConditional:
    """Test inline conditional parsing."""

    def test_sed_rubrica(self):
        doc = parse("[X]\n(sed rubrica 1960)\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, ConditionalLine)
        assert line.condition.expression == "sed rubrica 1960"

    def test_complex_condition(self):
        doc = parse("[X]\n(sed rubrica 1960 aut rubrica innovata)\n")
        line = doc.sections[0].body[0]
        assert isinstance(line, ConditionalLine)
        assert "aut" in line.condition.expression


class TestDocumentMethods:
    """Test Document helper methods."""

    def test_get_section(self):
        text = "[Rank]\nTest;;Duplex;;3\n\n[Oratio]\nDeus...\n"
        doc = parse(text)
        rank = doc.get_section("Rank")
        assert rank is not None
        assert rank.header.name == "Rank"

    def test_get_section_not_found(self):
        doc = parse("[Rank]\nTest;;Duplex;;3\n")
        assert doc.get_section("Oratio") is None

    def test_get_sections_with_rubric_variants(self):
        text = "[Rank]\nA;;B;;1\n" "[Rank] (rubrica 1960)\nC;;D;;2\n"
        doc = parse(text)
        # get_section returns the one without rubric
        plain = doc.get_section("Rank")
        assert plain is not None
        assert plain.header.rubric is None
        # get_sections returns all
        all_ranks = doc.get_sections("Rank")
        assert len(all_ranks) == 2

    def test_get_section_names(self):
        text = "[A]\nx\n[B]\ny\n[A] (rubrica 1960)\nz\n[C]\nw\n"
        doc = parse(text)
        assert doc.get_section_names() == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Integration tests with real DO files
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestParseRealFiles:
    """Test parsing of actual Divinum Officium Latin Missa files."""

    def test_epiphany(self):
        """Parse Epiphany (01-06) - a major feast with all standard sections."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        assert len(doc.sections) == 11
        names = doc.get_section_names()
        assert "Rank" in names
        assert "Rule" in names
        assert "Introitus" in names
        assert "Oratio" in names
        assert "Lectio" in names
        assert "Graduale" in names
        assert "Evangelium" in names
        assert "Offertorium" in names
        assert "Secreta" in names
        assert "Communio" in names
        assert "Postcommunio" in names

        # Check rank
        rank = doc.get_section("Rank")
        assert len(rank.body) == 1
        rv = rank.body[0]
        assert isinstance(rv, RankValue)
        assert rv.display_name == "In Epiphania Domini"
        assert rv.rank_class == "Duplex I classis"
        assert rv.weight == "7"

        # Check rule
        rule = doc.get_section("Rule")
        keywords = [
            line.keyword for line in rule.body if isinstance(line, RuleDirective)
        ]
        assert "Gloria" in keywords
        assert "Credo" in keywords

    def test_circumcision_cross_refs(self):
        """Parse Circumcision (01-01) - has many @cross-references."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-01.txt")
        # Check Introitus references Tempora/Nat30
        introitus = doc.get_section("Introitus")
        assert len(introitus.body) == 1
        ref = introitus.body[0]
        assert isinstance(ref, CrossRef)
        assert ref.file_ref == "Tempora/Nat30"

        # Check Commemoratio sections have rubric conditions
        comm_oratio = [
            s for s in doc.sections if s.header.name == "Commemoratio Oratio"
        ]
        assert len(comm_oratio) == 1
        assert comm_oratio[0].header.rubric is not None
        assert comm_oratio[0].header.rubric.expression == "rubrica tridentina"

    def test_holy_innocents_multiple_ranks(self):
        """Parse Holy Innocents (12-28) - has 3 rank variants with conditions."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "12-28.txt")
        rank = doc.get_section("Rank")
        rank_values = [line for line in rank.body if isinstance(line, RankValue)]
        conditionals = [line for line in rank.body if isinstance(line, ConditionalLine)]
        assert len(rank_values) == 3
        assert len(conditionals) == 2
        assert conditionals[0].condition.expression == "sed rubrica 196"
        assert conditionals[1].condition.expression == "sed rubrica tridentina"

    def test_advent_sunday(self):
        """Parse First Sunday of Advent - has GradualeF variant."""
        doc = parse_file(_MISSA_LATIN / "Tempora" / "Adv1-0.txt")
        names = doc.get_section_names()
        assert "GradualeF" in names
        assert "Officium" in names

    def test_easter_sunday(self):
        """Parse Easter Sunday - has Sequentia section."""
        doc = parse_file(_MISSA_LATIN / "Tempora" / "Pasc0-0.txt")
        names = doc.get_section_names()
        assert "Sequentia" in names

        # The Sequentia should have a scripture ref for the rubric
        seq = doc.get_section("Sequentia")
        scripture_refs = [line for line in seq.body if isinstance(line, ScriptureRef)]
        assert any("Sequentia dicitur" in r.body for r in scripture_refs)

    def test_christmas_dispatcher(self):
        """Parse Christmas (12-25) - a dispatcher with celebranda rule."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "12-25.txt")
        rule = doc.get_section("Rule")
        assert any(
            isinstance(line, RuleDirective) and "celebranda" in line.keyword
            for line in rule.body
        )

    def test_trinity_sunday_cross_refs(self):
        """Parse Trinity Sunday - has both standard content and @references."""
        doc = parse_file(_MISSA_LATIN / "Tempora" / "Pent01-0.txt")
        # Introitus is a self-reference
        introitus = doc.get_section("Introitus")
        assert len(introitus.body) == 1
        ref = introitus.body[0]
        assert isinstance(ref, CrossRef)

        # Ultima Evangelium cross-references another file
        ult = doc.get_section("Ultima Evangelium")
        assert ult is not None
        assert isinstance(ult.body[0], CrossRef)

    def test_ordo_preamble_only(self):
        """Parse Ordo.txt - has no [Section] headers, only preamble."""
        doc = parse_file(_MISSA_LATIN / "Ordo" / "Ordo.txt")
        assert len(doc.preamble) > 100
        assert len(doc.sections) == 0

    def test_prefationes_many_sections(self):
        """Parse Prefationes.txt - has 30+ preface sections."""
        doc = parse_file(_MISSA_LATIN / "Ordo" / "Prefationes.txt")
        assert len(doc.sections) > 30
        names = doc.get_section_names()
        assert "Nat" in names
        assert "Pasch" in names
        assert "Communis" in names

    def test_all_latin_missa_files_parse(self):
        """Every Latin Missa .txt file parses without error."""
        import glob

        failures = []
        total = 0
        for pattern in ["Sancti/*.txt", "Tempora/*.txt", "Commune/*.txt", "Ordo/*.txt"]:
            for f in glob.glob(str(_MISSA_LATIN / pattern)):
                total += 1
                try:
                    parse_file(f)
                except Exception as e:
                    failures.append(f"{os.path.basename(f)}: {e}")

        assert total > 1000, f"Expected 1000+ files, found {total}"
        assert failures == [], f"Parse failures:\n" + "\n".join(failures)
