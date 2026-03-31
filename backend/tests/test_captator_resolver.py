"""Tests for the Divinum Officium document resolver.

Tests the condition evaluator (vero), cross-reference resolution,
display marker filtering, and inline conditional processing.
"""

from pathlib import Path

import pytest

from sacrum.captator.parser import parse, parse_file
from sacrum.captator.parser.ast_nodes import (
    CrossRef,
    GloriaRef,
    LineKind,
    MacroRef,
    RankValue,
    ScriptureRef,
    SubroutineRef,
    TextLine,
    Versicle,
)
from sacrum.captator.resolver import (
    MassType,
    MissalConfig,
    OrderVariant,
    Rubric,
    resolve,
    vero,
)

# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------

_DO_BASE = (
    Path(__file__).parent.parent / "src" / "sacrum" / "divinum-officium" / "web" / "www"
)
_MISSA_LATIN = _DO_BASE / "missa" / "Latin"
_HAS_DATA = _MISSA_LATIN.is_dir() and any(_MISSA_LATIN.glob("Sancti/*.txt"))


# ---------------------------------------------------------------------------
# vero() evaluator tests
# ---------------------------------------------------------------------------


class TestVero:
    """Test the rubric condition evaluator."""

    def _cfg(self, rubric=Rubric.RUBRICAE_1960, **kwargs):
        return MissalConfig(rubric=rubric, **kwargs)

    # --- Rubric version conditions ---

    def test_rubrica_1960(self):
        assert vero("rubrica 1960", self._cfg(Rubric.RUBRICAE_1960)) is True
        assert vero("rubrica 1960", self._cfg(Rubric.TRIDENT_1570)) is False

    def test_rubrica_196_matches_1960(self):
        """'196' is a regex that matches '1960'."""
        assert vero("rubrica 196", self._cfg(Rubric.RUBRICAE_1960)) is True

    def test_rubrica_1955(self):
        assert vero("rubrica 1955", self._cfg(Rubric.RUBRICAE_1955)) is True
        assert vero("rubrica 1955", self._cfg(Rubric.RUBRICAE_1960)) is False

    def test_rubrica_tridentina(self):
        assert vero("rubrica tridentina", self._cfg(Rubric.TRIDENT_1570)) is True
        assert vero("rubrica tridentina", self._cfg(Rubric.TRIDENT_1910)) is True
        assert vero("rubrica tridentina", self._cfg(Rubric.RUBRICAE_1960)) is False

    # --- Order variant conditions ---

    def test_rubrica_monastica(self):
        cfg = self._cfg(order=OrderVariant.MONASTIC)
        assert vero("rubrica monastica", cfg) is True
        assert vero("rubrica monastica", self._cfg()) is False

    def test_rubrica_cisterciensis(self):
        cfg = self._cfg(order=OrderVariant.CISTERCIAN)
        assert vero("rubrica cisterciensis", cfg) is True

    def test_rubrica_praedicatorum(self):
        cfg = self._cfg(order=OrderVariant.DOMINICAN)
        assert vero("rubrica praedicatorum", cfg) is True

    # --- Boolean operators ---

    def test_aut_operator(self):
        """'aut' = OR: true if either branch is true."""
        assert (
            vero("rubrica 196 aut rubrica 1955", self._cfg(Rubric.RUBRICAE_1960))
            is True
        )
        assert (
            vero("rubrica 196 aut rubrica 1955", self._cfg(Rubric.RUBRICAE_1955))
            is True
        )
        assert (
            vero("rubrica 196 aut rubrica 1955", self._cfg(Rubric.TRIDENT_1570))
            is False
        )

    def test_nisi_operator(self):
        """'nisi' = unless: subsequent atoms in the branch must be false."""
        # "tridentine unless cistercian"
        cfg_trid = self._cfg(Rubric.TRIDENT_1570)
        cfg_cist = self._cfg(Rubric.TRIDENT_1570, order=OrderVariant.CISTERCIAN)
        assert vero("rubrica tridentina nisi rubrica cisterciensis", cfg_trid) is True
        assert vero("rubrica tridentina nisi rubrica cisterciensis", cfg_cist) is False

    def test_empty_condition_is_true(self):
        assert vero("", self._cfg()) is True

    # --- Tempore conditions ---

    def test_tempore_paschali(self):
        cfg = self._cfg(tempus_id="Octava Paschæ")
        assert vero("tempore paschali", cfg) is True
        cfg2 = self._cfg(tempus_id="Adventus")
        assert vero("tempore paschali", cfg2) is False

    def test_tempore_adventus(self):
        cfg = self._cfg(tempus_id="Adventus")
        assert vero("tempore Adventus", cfg) is True

    def test_post_septuagesimam(self):
        cfg = self._cfg(tempus_id="Quadragesimæ")
        assert vero("post septuagesimam", cfg) is True
        cfg2 = self._cfg(tempus_id="post Pentecosten")
        assert vero("post septuagesimam", cfg2) is False

    # --- Feria conditions ---

    def test_feria(self):
        cfg = self._cfg(day_of_week=2)  # Monday
        assert vero("feria secunda", cfg) is True
        assert vero("feria prima", cfg) is False


# ---------------------------------------------------------------------------
# Section variant selection tests
# ---------------------------------------------------------------------------


class TestSectionVariants:
    """Test that the resolver selects correct section variants."""

    def test_keep_unconditional_when_condition_fails(self):
        text = (
            "[Rank]\nDefault;;Duplex;;3\n\n[Rank] (rubrica 1960)\nSpecial;;Duplex;;5\n"
        )
        doc = parse(text)
        config = MissalConfig(rubric=Rubric.TRIDENT_1570)
        resolved = resolve(doc, config, "/nonexistent")
        rank = next(s for s in resolved.sections if s.header.name == "Rank")
        rv = rank.body[0]
        assert isinstance(rv, RankValue)
        assert rv.display_name == "Default"

    def test_replace_with_conditional_when_condition_passes(self):
        text = (
            "[Rank]\nDefault;;Duplex;;3\n\n[Rank] (rubrica 1960)\nSpecial;;Duplex;;5\n"
        )
        doc = parse(text)
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, "/nonexistent")
        rank = next(s for s in resolved.sections if s.header.name == "Rank")
        rv = rank.body[0]
        assert isinstance(rv, RankValue)
        assert rv.display_name == "Special"

    def test_conditional_only_section_removed_when_false(self):
        """A section that only has a conditional variant should be absent when false."""
        text = "[Commemoratio Oratio] (rubrica tridentina)\n!Pro S. Stephano\n"
        doc = parse(text)
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, "/nonexistent")
        assert len(resolved.sections) == 0


# ---------------------------------------------------------------------------
# Cross-reference resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestCrossRefResolution:
    """Test @-reference resolution with real files."""

    def test_simple_file_ref(self):
        """@Tempora/Nat30 resolves to the Introitus of that file."""
        text = "[Introitus]\n@Tempora/Nat30\n"
        doc = parse(text)
        config = MissalConfig()
        resolved = resolve(doc, config, _MISSA_LATIN)
        introitus = resolved.sections[0]
        # Should have been replaced with actual content
        assert len(introitus.body) > 1
        assert not any(isinstance(l, CrossRef) for l in introitus.body)

    def test_file_and_section_ref(self):
        """@Sancti/08-03:Oratio resolves to the Oratio section of that file."""
        text = "[Oratio]\n@Sancti/08-03:Oratio\n"
        doc = parse(text)
        config = MissalConfig()
        resolved = resolve(doc, config, _MISSA_LATIN)
        oratio = resolved.sections[0]
        assert len(oratio.body) > 0
        # The resolved content should contain text (the actual prayer)
        has_text = any(isinstance(l, TextLine) for l in oratio.body)
        assert has_text

    def test_chained_refs(self):
        """Circumcision (01-01) has @refs that reference other files."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-01.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        # Introitus should be resolved (was @Tempora/Nat30)
        introitus = next(s for s in resolved.sections if s.header.name == "Introitus")
        assert any(isinstance(l, Versicle) for l in introitus.body)

    def test_unresolvable_ref_kept(self):
        """References to nonexistent files are kept as-is."""
        text = "[X]\n@Nonexistent/File\n"
        doc = parse(text)
        config = MissalConfig()
        resolved = resolve(doc, config, _MISSA_LATIN)
        assert len(resolved.sections[0].body) == 1
        assert isinstance(resolved.sections[0].body[0], CrossRef)


# ---------------------------------------------------------------------------
# Display marker filtering tests
# ---------------------------------------------------------------------------


class TestDisplayMarkers:
    """Test !*S/!*R/!*D display marker filtering."""

    def test_solemn_marker_shown_for_solemn(self):
        text = "[X]\n!*S\nSolemn content\nMore solemn\n"
        doc = parse(text)
        config = MissalConfig(mass_type=MassType.SOLEMN)
        resolved = resolve(doc, config, "/nonexistent")
        body = resolved.sections[0].body
        assert any(isinstance(l, TextLine) and "Solemn content" in l.body for l in body)

    def test_solemn_marker_hidden_for_read(self):
        text = "[X]\n!*S\nSolemn only content\n!*R\nRead content here\n"
        doc = parse(text)
        config = MissalConfig(mass_type=MassType.READ)
        resolved = resolve(doc, config, "/nonexistent")
        body = resolved.sections[0].body
        has_solemn = any(
            isinstance(l, TextLine) and "Solemn only" in l.body for l in body
        )
        has_read = any(
            isinstance(l, TextLine) and "Read content" in l.body for l in body
        )
        assert not has_solemn
        assert has_read

    def test_defunctorum_marker(self):
        text = "[X]\n!*D\nRequiem text\n!*nD\nNon-requiem text\n"
        doc = parse(text)
        # Requiem config
        config_req = MissalConfig(mass_type=MassType.REQUIEM)
        resolved_req = resolve(doc, config_req, "/nonexistent")
        body_req = resolved_req.sections[0].body
        has_requiem = any(
            isinstance(l, TextLine) and "Requiem text" in l.body for l in body_req
        )
        has_non_req = any(
            isinstance(l, TextLine) and "Non-requiem" in l.body for l in body_req
        )
        assert has_requiem
        assert not has_non_req

        # Non-requiem config
        config_normal = MissalConfig(mass_type=MassType.READ)
        resolved_normal = resolve(doc, config_normal, "/nonexistent")
        body_normal = resolved_normal.sections[0].body
        has_requiem_n = any(
            isinstance(l, TextLine) and "Requiem text" in l.body for l in body_normal
        )
        has_non_req_n = any(
            isinstance(l, TextLine) and "Non-requiem" in l.body for l in body_normal
        )
        assert not has_requiem_n
        assert has_non_req_n


# ---------------------------------------------------------------------------
# Inline conditional tests
# ---------------------------------------------------------------------------


class TestInlineConditionals:
    """Test inline (sed ...) conditional processing."""

    def test_sed_replaces_preceding_line(self):
        """(sed condition dicitur) replaces the preceding line when true."""
        text = (
            "[Rank]\nOriginal;;Duplex;;3\n(sed rubrica 1960)\nReplacement;;Duplex;;5\n"
        )
        doc = parse(text)
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, "/nonexistent")
        rank = next(s for s in resolved.sections if s.header.name == "Rank")
        rvs = [l for l in rank.body if isinstance(l, RankValue)]
        assert len(rvs) == 1
        assert rvs[0].weight == "5"

    def test_sed_keeps_preceding_when_false(self):
        """When (sed ...) condition is false, keep the original line."""
        text = (
            "[Rank]\nOriginal;;Duplex;;3\n(sed rubrica 1960)\nReplacement;;Duplex;;5\n"
        )
        doc = parse(text)
        config = MissalConfig(rubric=Rubric.TRIDENT_1570)
        resolved = resolve(doc, config, "/nonexistent")
        rank = next(s for s in resolved.sections if s.header.name == "Rank")
        rvs = [l for l in rank.body if isinstance(l, RankValue)]
        assert len(rvs) == 1
        assert rvs[0].weight == "3"


# ---------------------------------------------------------------------------
# Integration tests with real files
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestRealFileResolution:
    """Integration tests: resolve real DO Missa Latin files."""

    def test_epiphany_fully_resolved(self):
        """Epiphany (01-06) is self-contained — no @refs to resolve."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        assert len(resolved.sections) == 11
        # All sections should have content (no empty sections after resolution)
        for s in resolved.sections:
            assert len(s.body) > 0, f"Section [{s.header.name}] is empty"

    def test_circumcision_1960_no_commemorations(self):
        """Circumcision (01-01) with 1960: no Commemoratio sections."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-01.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        names = [s.header.name for s in resolved.sections]
        assert not any("Commemoratio" in n for n in names)

    def test_circumcision_tridentine_has_commemorations(self):
        """Circumcision (01-01) with Tridentine: has Commemoratio sections."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-01.txt")
        config = MissalConfig(rubric=Rubric.TRIDENT_1570)
        resolved = resolve(doc, config, _MISSA_LATIN)
        names = [s.header.name for s in resolved.sections]
        assert any("Commemoratio" in n for n in names)

    def test_holy_innocents_rank_1960(self):
        """Holy Innocents (12-28) with 1960: specific rank value selected."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "12-28.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        rank = next(s for s in resolved.sections if s.header.name == "Rank")
        rvs = [l for l in rank.body if isinstance(l, RankValue)]
        assert len(rvs) == 1
        assert rvs[0].rank_class == "Duplex II class"
        assert rvs[0].weight == "5"

    def test_holy_innocents_rank_tridentine(self):
        """Holy Innocents (12-28) with Tridentine: octave rank selected."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "12-28.txt")
        config = MissalConfig(rubric=Rubric.TRIDENT_1570)
        resolved = resolve(doc, config, _MISSA_LATIN)
        rank = next(s for s in resolved.sections if s.header.name == "Rank")
        rvs = [l for l in rank.body if isinstance(l, RankValue)]
        assert len(rvs) == 1
        assert "cum octava" in rvs[0].rank_class

    def test_advent_first_sunday_resolved(self):
        """First Sunday of Advent has no @refs — resolves cleanly."""
        doc = parse_file(_MISSA_LATIN / "Tempora" / "Adv1-0.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        # Should have standard Mass sections
        names = [s.header.name for s in resolved.sections]
        assert "Introitus" in names
        assert "Oratio" in names
        assert "Evangelium" in names

    def test_assumption_rank_variant(self):
        """Assumption (08-15): has (sed rubrica 1960) inline in Rank."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "08-15.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        rank = next(s for s in resolved.sections if s.header.name == "Rank")
        rvs = [l for l in rank.body if isinstance(l, RankValue)]
        assert len(rvs) == 1
        # 1960 version should NOT have "cum Octava"
        assert "Octava" not in rvs[0].rank_class


# ---------------------------------------------------------------------------
# Self-reference (@:Section) resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestSelfRefResolution:
    """Test resolution of self-references (@:SectionName)."""

    def test_cathedra_petri_self_refs(self):
        """Cathedra S. Petri (02-22) uses @:Oratio Petri and @:Oratio Pauli."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "02-22.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        oratio = next(s for s in resolved.sections if s.header.name == "Oratio")
        # Self-refs should be resolved — no CrossRef nodes remain
        has_crossref = any(isinstance(l, CrossRef) for l in oratio.body)
        assert not has_crossref
        # The actual prayer text should be present
        has_text = any(isinstance(l, TextLine) for l in oratio.body)
        assert has_text

    def test_self_ref_with_substitution_1960(self):
        """S. John of Cross (11-24) with 1960: keeps 'Doctorem' title."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "11-24.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        oratio = next(s for s in resolved.sections if s.header.name == "Oratio")
        text = " ".join(l.raw for l in oratio.body)
        assert "Doctorem" in text

    def test_self_ref_with_substitution_tridentine(self):
        """S. John of Cross (11-24) with Tridentine: strips 'Doctorem'."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "11-24.txt")
        config = MissalConfig(rubric=Rubric.TRIDENT_1570)
        resolved = resolve(doc, config, _MISSA_LATIN)
        oratio = next(s for s in resolved.sections if s.header.name == "Oratio")
        text = " ".join(l.raw for l in oratio.body)
        assert "Doctorem" not in text


# ---------------------------------------------------------------------------
# $ macro expansion tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestMacroExpansion:
    """Test expansion of $ macros from Prayers.txt."""

    def test_per_dominum_expanded(self):
        """$Per Dominum is replaced by the prayer conclusion text."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        postcom = next(s for s in resolved.sections if s.header.name == "Postcommunio")
        # Should not have any MacroRef nodes
        has_macro = any(isinstance(l, MacroRef) for l in postcom.body)
        assert not has_macro
        # Should have the expanded text with "Per Dóminum"
        text = " ".join(l.raw for l in postcom.body)
        assert "Per Dóminum nostrum" in text

    def test_qui_tecum_expanded(self):
        """$Qui tecum is replaced by the correct conclusion."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        secreta = next(s for s in resolved.sections if s.header.name == "Secreta")
        text = " ".join(l.raw for l in secreta.body)
        assert "Qui tecum vivit" in text

    def test_per_eumdem_expanded(self):
        """$Per eumdem is replaced by the correct conclusion."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        oratio = next(s for s in resolved.sections if s.header.name == "Oratio")
        text = " ".join(l.raw for l in oratio.body)
        assert "Per eúndem Dóminum" in text

    def test_per_dominum_with_trailing_period(self):
        """$Per Dominum. (with period) also resolves correctly."""
        doc = parse_file(_MISSA_LATIN / "Tempora" / "Pent01-0a.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        oratio = next(s for s in resolved.sections if s.header.name == "Oratio")
        has_macro = any(isinstance(l, MacroRef) for l in oratio.body)
        assert not has_macro


# ---------------------------------------------------------------------------
# & subroutine expansion tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestSubroutineExpansion:
    """Test expansion of static & subroutines."""

    def test_gloria_expanded_in_introitus(self):
        """&Gloria in Introitus is replaced by Gloria Patri text."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        introitus = next(s for s in resolved.sections if s.header.name == "Introitus")
        # No GloriaRef nodes should remain
        has_gloria_ref = any(isinstance(l, GloriaRef) for l in introitus.body)
        assert not has_gloria_ref
        # Gloria Patri text should be present
        text = " ".join(l.raw for l in introitus.body)
        assert "Glória Patri" in text

    def test_dynamic_subroutines_kept(self):
        """Dynamic &introitus, &collect etc. in Ordo are kept as-is."""
        doc = parse_file(_MISSA_LATIN / "Ordo" / "Propers.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960)
        resolved = resolve(doc, config, _MISSA_LATIN)
        # Dynamic subroutines should still be present as SubroutineRef nodes
        has_dynamic = any(isinstance(l, SubroutineRef) for l in resolved.preamble)
        assert has_dynamic


# ---------------------------------------------------------------------------
# Language layering tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestLanguageLayering:
    """Test that macros expand in the configured language."""

    def test_per_dominum_latin(self):
        """Latin config expands $Per Dominum in Latin."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960, language="Latin")
        resolved = resolve(doc, config, _MISSA_LATIN)
        postcom = next(s for s in resolved.sections if s.header.name == "Postcommunio")
        text = " ".join(l.raw for l in postcom.body)
        assert "Per Dóminum nostrum Jesum Christum" in text

    def test_per_dominum_english(self):
        """English config expands $Per Dominum in English."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960, language="English")
        resolved = resolve(doc, config, _MISSA_LATIN)
        postcom = next(s for s in resolved.sections if s.header.name == "Postcommunio")
        text = " ".join(l.raw for l in postcom.body)
        assert "Through Jesus Christ" in text

    def test_per_dominum_espanol(self):
        """Espanol config expands $Per Dominum in Spanish."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960, language="Espanol")
        resolved = resolve(doc, config, _MISSA_LATIN)
        postcom = next(s for s in resolved.sections if s.header.name == "Postcommunio")
        text = " ".join(l.raw for l in postcom.body)
        assert "Por nuestro Se" in text  # "Por nuestro Señor"

    def test_gloria_english(self):
        """English config expands &Gloria in English."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960, language="English")
        resolved = resolve(doc, config, _MISSA_LATIN)
        introitus = next(s for s in resolved.sections if s.header.name == "Introitus")
        text = " ".join(l.raw for l in introitus.body)
        assert "Glory be to the Father" in text

    def test_unknown_language_falls_back_to_latin(self):
        """An unknown language gracefully falls back to Latin."""
        doc = parse_file(_MISSA_LATIN / "Sancti" / "01-06.txt")
        config = MissalConfig(rubric=Rubric.RUBRICAE_1960, language="Klingon")
        resolved = resolve(doc, config, _MISSA_LATIN)
        postcom = next(s for s in resolved.sections if s.header.name == "Postcommunio")
        text = " ".join(l.raw for l in postcom.body)
        # Falls back to Latin
        assert "Per Dóminum nostrum Jesum Christum" in text
