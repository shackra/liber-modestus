"""Tests for the Mass assembly module."""

from datetime import date
from pathlib import Path

import pytest

from captator.assembly import assemble_mass
from captator.directorium import get_mass_day
from captator.parser.ast_nodes import SubroutineRef, TextLine
from captator.resolver import MassType, MissalConfig, Rubric

_DO_BASE = Path(__file__).parent.parent / "src" / "divinum-officium" / "web" / "www"
_TABULAE = _DO_BASE / "Tabulae"
_MISSA = _DO_BASE / "missa" / "Latin"
_HAS_DATA = _TABULAE.is_dir() and _MISSA.is_dir()


def _get_propers(y: int, m: int, d: int, rubric: Rubric = Rubric.RUBRICAE_1960):
    config = MissalConfig(rubric=rubric, mass_type=MassType.READ)
    day = get_mass_day(date(y, m, d), config, _TABULAE, _MISSA)
    return day.resolved_document, config


def _all_lines(doc):
    lines = list(doc.preamble)
    for s in doc.sections:
        lines.extend(s.body)
    return lines


def _text(doc):
    return " ".join(l.raw for l in _all_lines(doc))


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestAssembly:
    """Test that assemble_mass produces a complete Mass."""

    def test_propers_inserted(self):
        """All proper subroutines (&introitus, &collect, etc.) are resolved."""
        propers, config = _get_propers(2025, 1, 6)
        complete = assemble_mass(propers, config, _MISSA)

        proper_names = {
            "introitus",
            "collect",
            "lectio",
            "graduale",
            "evangelium",
            "offertorium",
            "secreta",
            "communio",
            "postcommunio",
        }
        remaining = [
            l.function_name
            for l in _all_lines(complete)
            if isinstance(l, SubroutineRef) and l.function_name in proper_names
        ]
        assert remaining == [], f"Unresolved propers: {remaining}"

    def test_more_lines_than_propers(self):
        """The assembled Mass has more lines than just the propers."""
        propers, config = _get_propers(2025, 1, 6)
        complete = assemble_mass(propers, config, _MISSA)

        proper_count = sum(len(s.body) for s in propers.sections)
        total_count = len(_all_lines(complete))
        assert total_count > proper_count * 2

    def test_contains_canon(self):
        """The assembled Mass includes the Canon (Te igitur)."""
        propers, config = _get_propers(2025, 1, 6)
        complete = assemble_mass(propers, config, _MISSA)
        full = _text(complete)
        assert "Te ígitur" in full or "Te igitur" in full

    def test_contains_proper_introit(self):
        """The Epiphany introit text appears in the assembled Mass."""
        propers, config = _get_propers(2025, 1, 6)
        complete = assemble_mass(propers, config, _MISSA)
        full = _text(complete)
        assert "advénit dominátor" in full

    def test_contains_proper_gospel(self):
        """The day's Gospel text appears in the assembled Mass."""
        propers, config = _get_propers(2025, 1, 6)
        complete = assemble_mass(propers, config, _MISSA)
        full = _text(complete)
        # Epiphany Gospel: Matthew 2:1-12 (the Magi)
        assert "Magi" in full or "Magos" in full or "stellam" in full


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestPreface:
    """Test that the correct Preface is selected."""

    def test_epiphany_preface(self):
        """Epiphany gets the Epiphany preface (immortalitatis)."""
        propers, config = _get_propers(2025, 1, 6)
        config = MissalConfig(
            rubric=Rubric.RUBRICAE_1960,
            mass_type=MassType.READ,
            tempus_id="post Epiphaniam",
        )
        complete = assemble_mass(propers, config, _MISSA)
        full = _text(complete)
        # The Epiphany preface contains "immortalitatis"
        assert "immortalitátis" in full or "immortalitatis" in full

    def test_preface_always_inserted(self):
        """The assembled Mass always contains a preface (Vere dignum)."""
        propers, _ = _get_propers(2025, 7, 6)
        config = MissalConfig(
            rubric=Rubric.RUBRICAE_1960,
            mass_type=MassType.READ,
            tempus_id="post Pentecosten",
        )
        complete = assemble_mass(propers, config, _MISSA)
        full = _text(complete)
        assert "Vere dignum et justum" in full


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestCommunicantes:
    """Test that the correct Communicantes variant is selected."""

    def test_1962_has_joseph(self):
        """The 1962 Missal includes St. Joseph in the Communicantes."""
        propers, _ = _get_propers(2025, 1, 6)
        config = MissalConfig(
            rubric=Rubric.RUBRICAE_1960,
            mass_type=MassType.READ,
            tempus_id="post Epiphaniam",
        )
        complete = assemble_mass(propers, config, _MISSA)
        full = _text(complete)
        assert "Joseph" in full

    def test_tridentine_no_joseph(self):
        """Pre-1962 editions do NOT include St. Joseph in the Communicantes."""
        propers, _ = _get_propers(2025, 1, 6, Rubric.TRIDENT_1570)
        config = MissalConfig(
            rubric=Rubric.TRIDENT_1570,
            mass_type=MassType.READ,
            tempus_id="post Epiphaniam",
        )
        complete = assemble_mass(propers, config, _MISSA)
        # Find the Communicantes line specifically
        comm_lines = [
            l
            for l in _all_lines(complete)
            if "Communicántes" in l.raw or "Communicantes" in l.raw
        ]
        comm_text = " ".join(l.raw for l in comm_lines)
        assert "Joseph" not in comm_text


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestOrdoVariants:
    """Test different Ordo (canon) variants."""

    def test_standard_ordo(self):
        """Standard Roman Ordo loads without error."""
        propers, config = _get_propers(2025, 1, 6)
        complete = assemble_mass(propers, config, _MISSA, ordo="Ordo")
        assert len(_all_lines(complete)) > 100

    def test_dominican_ordo(self):
        """Dominican Ordo loads without error."""
        propers, config = _get_propers(2025, 1, 6)
        complete = assemble_mass(propers, config, _MISSA, ordo="OrdoOP")
        assert len(_all_lines(complete)) > 50

    def test_invalid_ordo_falls_back(self):
        """An invalid Ordo name falls back to the standard Ordo."""
        propers, config = _get_propers(2025, 1, 6)
        complete = assemble_mass(propers, config, _MISSA, ordo="NonExistent")
        assert len(_all_lines(complete)) > 100
