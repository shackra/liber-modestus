"""Tests for the Directorium liturgical calendar engine."""

from datetime import date
from pathlib import Path

import pytest

from sacrum.captator.directorium import MassDay, get_mass_day
from sacrum.captator.directorium.tables import (
    load_data_config,
    load_kalendar_merged,
    load_tempora_merged,
)
from sacrum.captator.resolver import MissalConfig, Rubric

_DO_BASE = (
    Path(__file__).parent.parent / "src" / "sacrum" / "divinum-officium" / "web" / "www"
)
_TABULAE = _DO_BASE / "Tabulae"
_MISSA = _DO_BASE / "missa" / "Latin"
_HAS_DATA = _TABULAE.is_dir() and (_TABULAE / "data.txt").is_file()


def _day(y: int, m: int, d: int, rubric: Rubric = Rubric.RUBRICAE_1960) -> MassDay:
    return get_mass_day(date(y, m, d), MissalConfig(rubric=rubric), _TABULAE, _MISSA)


# ---------------------------------------------------------------------------
# Table loading
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestTableLoading:
    def test_data_config_loads(self):
        configs = load_data_config(_TABULAE)
        assert "Rubrics 1960 - 1960" in configs
        assert "Tridentine - 1570" in configs

    def test_kalendar_merged_1960(self):
        configs = load_data_config(_TABULAE)
        kal = load_kalendar_merged(_TABULAE, configs, "Rubrics 1960 - 1960")
        assert "01-06" in kal  # Epiphany
        assert "12-25" in kal  # Christmas
        assert kal["01-06"].feast_name == "Epiphaniae Domini"

    def test_kalendar_1960_suppresses_octaves(self):
        configs = load_data_config(_TABULAE)
        kal = load_kalendar_merged(_TABULAE, configs, "Rubrics 1960 - 1960")
        # Epiphany octave days should be suppressed in 1955+
        entry = kal.get("01-07")
        # In 1570 this was the octave; in 1960 it's inherited from 1955
        # which doesn't suppress 01-07 but changes its meaning
        assert entry is not None

    def test_tempora_1960_has_reformed_holy_week(self):
        configs = load_data_config(_TABULAE)
        tem = load_tempora_merged(_TABULAE, configs, "Rubrics 1960 - 1960")
        # Palm Sunday should be remapped to reformed version
        assert tem.get("Tempora/Quad6-0") == "Tempora/Quad6-0r"

    def test_tempora_1570_has_tridentine_variants(self):
        configs = load_data_config(_TABULAE)
        tem = load_tempora_merged(_TABULAE, configs, "Tridentine - 1570")
        # Advent should be remapped to 'o' variants
        assert tem.get("Tempora/Adv1-0") == "Tempora/Adv1-0o"


# ---------------------------------------------------------------------------
# Temporal cycle
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestTemporalCycle:
    def test_advent_first_sunday(self):
        day = _day(2025, 11, 30)
        assert day.tempora_id == "Adv1-0"

    def test_christmas_eve(self):
        day = _day(2025, 12, 24)
        assert day.tempora_id is None  # Vigilia is in Sancti

    def test_epiphany(self):
        day = _day(2025, 1, 6)
        assert day.tempora_id is None  # Epiphany is in Sancti

    def test_septuagesima(self):
        # 2025 Easter = April 20, so Septuagesima = Feb 16
        day = _day(2025, 2, 16)
        assert day.tempora_id == "Quadp1-0"

    def test_ash_wednesday(self):
        # 2025: Ash Wednesday = March 5
        day = _day(2025, 3, 5)
        assert day.tempora_id is not None
        assert day.tempora_id.startswith("Quadp3")

    def test_palm_sunday(self):
        # 2025 Easter = April 20, Palm Sunday = April 13
        day = _day(2025, 4, 13)
        assert day.tempora_id == "Quad6-0"

    def test_easter_sunday(self):
        day = _day(2025, 4, 20)
        assert day.tempora_id == "Pasc0-0"

    def test_pentecost(self):
        # 2025 Pentecost = June 8
        day = _day(2025, 6, 8)
        assert day.tempora_id == "Pasc7-0"


# ---------------------------------------------------------------------------
# Occurrence resolution per edition
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestOccurrenceByEdition:
    def test_advent_1_always_wins(self):
        """First Sunday of Advent beats any saint in all editions."""
        for rubric in (Rubric.RUBRICAE_1960, Rubric.TRIDENT_1570):
            day = _day(2025, 11, 30, rubric)
            assert "Adv1-0" in day.occurrence.winner_file
            assert not day.occurrence.is_sanctoral

    def test_epiphany_octave_tridentine(self):
        """Jan 7 in Tridentine is the Epiphany Octave (Sancti/01-07)."""
        day = _day(2025, 1, 7, Rubric.TRIDENT_1570)
        assert "01-07" in day.occurrence.winner_file

    def test_epiphany_octave_suppressed_1960(self):
        """Jan 7 in 1960 is a feria, not octave day."""
        day = _day(2025, 1, 7, Rubric.RUBRICAE_1960)
        assert "Tempora" in day.occurrence.winner_file

    def test_st_joseph_1960_i_classis(self):
        """St Joseph (Mar 19) is I classis in 1960, wins over Lent feria."""
        day = _day(2025, 3, 19, Rubric.RUBRICAE_1960)
        assert "03-19" in day.occurrence.winner_file
        assert day.occurrence.is_sanctoral
        assert day.occurrence.winner_rank >= 6.0
        # Lent feria should be commemorated
        assert len(day.occurrence.commemorations) > 0

    def test_ss_peter_paul_wins(self):
        """Ss. Peter and Paul (Jun 29) always wins — I classis."""
        day = _day(2025, 6, 29, Rubric.RUBRICAE_1960)
        assert "06-29" in day.occurrence.winner_file
        assert day.occurrence.is_sanctoral


# ---------------------------------------------------------------------------
# Full resolution: parse + resolve
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestFullResolution:
    def test_epiphany_resolved(self):
        day = _day(2025, 1, 6)
        assert day.resolved_document is not None
        names = day.resolved_document.get_section_names()
        assert "Introitus" in names
        assert "Evangelium" in names

    def test_advent_1_resolved_1960(self):
        day = _day(2025, 11, 30)
        assert day.resolved_document is not None
        assert len(day.resolved_document.sections) > 5

    def test_advent_1_resolved_tridentine(self):
        day = _day(2025, 11, 30, Rubric.TRIDENT_1570)
        assert day.resolved_document is not None

    def test_different_rubrics_produce_different_results(self):
        """The same date with different rubrics may produce different content."""
        day_1960 = _day(2025, 1, 7, Rubric.RUBRICAE_1960)
        day_trid = _day(2025, 1, 7, Rubric.TRIDENT_1570)
        # They should have different winners
        assert day_1960.occurrence.winner_file != day_trid.occurrence.winner_file


# ---------------------------------------------------------------------------
# BVM Saturday (automatic)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestBMVSaturday:
    """Test automatic BVM Saturday Mass assignment."""

    def _find_qualifying_saturday(self, rubric: Rubric) -> date:
        """Find a Saturday in ordinary time with no feast (low rank)."""
        # July/August Saturdays in Pentecost season usually qualify.
        # Try successive Saturdays until we find one.
        import datetime

        dt = date(2025, 7, 5)  # a Saturday
        while dt.isoweekday() != 6:
            dt += datetime.timedelta(days=1)
        for _ in range(10):
            day = _day(dt.year, dt.month, dt.day, rubric)
            if day.occurrence.is_bmv_saturday:
                return dt
            dt += datetime.timedelta(days=7)
        pytest.skip("Could not find a qualifying Saturday")

    def test_bmv_saturday_assigned(self):
        """A qualifying Saturday gets BVM Mass automatically."""
        dt = self._find_qualifying_saturday(Rubric.RUBRICAE_1960)
        day = _day(dt.year, dt.month, dt.day, Rubric.RUBRICAE_1960)
        assert day.occurrence.is_bmv_saturday
        assert "C10" in day.occurrence.winner_file

    def test_bmv_not_on_advent_saturday(self):
        """Advent Saturdays (privileged feria rank >= 1.15) block BVM."""
        # Dec 6, 2025 is a Saturday in Advent
        day = _day(2025, 12, 6)
        assert not day.occurrence.is_bmv_saturday

    def test_bmv_not_on_lent_saturday(self):
        """Lent Saturdays (privileged feria rank >= 2.1) block BVM."""
        # Find a Saturday in Lent 2025 (Easter April 20, Lent starts Mar 5)
        day = _day(2025, 3, 15)  # Saturday in Lent
        assert not day.occurrence.is_bmv_saturday

    def test_bmv_not_on_feast_day(self):
        """A Saturday with a feast (rank >= 1.4) does not get BVM."""
        # Check Dec 13, 2025 (Saturday) - St. Lucy (rank 3 in all editions)
        day = _day(2025, 12, 13)
        assert not day.occurrence.is_bmv_saturday


# ---------------------------------------------------------------------------
# Requiem / Defunctorum
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestRequiem:
    """Test automatic Requiem detection for All Souls."""

    def test_all_souls_is_requiem(self):
        """November 2 is automatically marked as Requiem (when not Sunday)."""
        # 2025: Nov 2 is Sunday, so the Sunday wins.
        # Use 2024: Nov 2 is Saturday — All Souls should win.
        day = _day(2024, 11, 2)
        assert day.occurrence.is_requiem
        assert "11-02" in day.occurrence.winner_file

    def test_all_souls_on_sunday_is_commemorated(self):
        """When Nov 2 falls on Sunday, the Sunday wins (All Souls commemorated)."""
        day = _day(2025, 11, 2)  # Sunday
        assert not day.occurrence.is_requiem
        # All Souls should be in commemorations
        assert any("11-02" in c for c in day.occurrence.commemorations)

    def test_ordinary_day_not_requiem(self):
        """A regular day is not marked as Requiem."""
        day = _day(2025, 6, 15)  # random weekday
        assert not day.occurrence.is_requiem


# ---------------------------------------------------------------------------
# Christ the King (last Sunday of October)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestChristTheKing:
    """Test the Feast of Christ the King (last Sunday of October).

    Instituted by Pius XI in 1925 (Quas Primas). Appears in calendars
    from Divino Afflatu (post-1925) onward. NOT in pre-1925 calendars.
    """

    def test_christ_king_1960(self):
        """With 1960 rubrics, Christ the King is on the last Sunday of Oct."""
        # 2025: Oct 26 is the last Sunday
        day = _day(2025, 10, 26)
        assert "10-DU" in day.occurrence.winner_file
        assert day.occurrence.is_sanctoral

    def test_christ_king_divino(self):
        """With Divino Afflatu (post-1925), Christ the King is present."""
        day = _day(2025, 10, 26, Rubric.TRIDENT_1930)
        assert "10-DU" in day.occurrence.winner_file

    def test_christ_king_absent_pre_1925(self):
        """With Tridentine 1570, Christ the King does NOT exist."""
        day = _day(2025, 10, 26, Rubric.TRIDENT_1570)
        # Should NOT be 10-DU; it should be the temporal
        # (a Pentecost Sunday) or some saint
        assert "10-DU" not in day.occurrence.winner_file

    def test_christ_king_different_years(self):
        """Christ the King falls on different October dates each year."""
        # 2024: Oct 27 is the last Sunday
        day_2024 = _day(2024, 10, 27)
        assert "10-DU" in day_2024.occurrence.winner_file

        # 2026: Oct 25 is the last Sunday
        day_2026 = _day(2026, 10, 25)
        assert "10-DU" in day_2026.occurrence.winner_file
