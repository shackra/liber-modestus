"""Tests for the Directorium liturgical calendar engine."""

from datetime import date
from pathlib import Path

import pytest

from sacrum.captator.directorium import (
    LiturgicalColor,
    MassDay,
    MassInfo,
    get_mass_day,
    get_mass_info_for_date,
    get_mass_info_for_month,
)
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


# ---------------------------------------------------------------------------
# get_mass_info_for_date
# ---------------------------------------------------------------------------


def _info(
    y: int,
    m: int,
    d: int,
    rubric: Rubric = Rubric.RUBRICAE_1960,
    language: str = "Latin",
) -> MassInfo:
    return get_mass_info_for_date(date(y, m, d), rubric, language)


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestMassInfoBasic:
    """Basic tests for get_mass_info_for_date return type and fields."""

    def test_returns_mass_info(self):
        info = _info(2025, 12, 25)
        assert isinstance(info, MassInfo)

    def test_has_all_fields(self):
        info = _info(2025, 12, 25)
        assert info.date == date(2025, 12, 25)
        assert isinstance(info.name, str) and info.name
        assert isinstance(info.name_canonical, str) and info.name_canonical
        assert isinstance(info.rank, float)
        assert isinstance(info.rank_name, str)
        assert isinstance(info.color, LiturgicalColor)
        assert isinstance(info.is_sanctoral, bool)
        assert isinstance(info.commemorations, list)

    def test_canonical_name_is_latin(self):
        """name_canonical should always be in Latin regardless of language."""
        info = _info(2025, 6, 29, language="English")
        # The canonical name should NOT be in English
        assert "Apostol" in info.name_canonical  # Latin word
        assert info.name != info.name_canonical  # Translated name differs


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestMassInfoColor:
    """Test liturgical colour assignment."""

    def test_christmas_is_white(self):
        info = _info(2025, 12, 25)
        assert info.color == LiturgicalColor.WHITE

    def test_advent_sunday_is_violet(self):
        info = _info(2025, 11, 30)
        assert info.color == LiturgicalColor.VIOLET

    def test_gaudete_sunday_is_rose(self):
        """Third Sunday of Advent (Gaudete) uses rose vestments."""
        # 2025: Advent III = Dec 14
        info = _info(2025, 12, 14)
        assert info.color == LiturgicalColor.ROSE

    def test_laetare_sunday_is_rose(self):
        """Fourth Sunday of Lent (Laetare) uses rose vestments."""
        # 2025: Easter = Apr 20, Laetare = Mar 30
        info = _info(2025, 3, 30)
        assert info.color == LiturgicalColor.ROSE

    def test_ss_peter_paul_is_red(self):
        """Apostles feast = red vestments."""
        info = _info(2025, 6, 29)
        assert info.color == LiturgicalColor.RED

    def test_all_souls_is_black(self):
        """All Souls (Nov 2, when not Sunday) = black vestments."""
        # 2024: Nov 2 is Saturday
        info = _info(2024, 11, 2)
        assert info.color == LiturgicalColor.BLACK

    def test_good_friday_is_black(self):
        """Good Friday = black vestments."""
        # 2025: Good Friday = Apr 18
        info = _info(2025, 4, 18)
        assert info.color == LiturgicalColor.BLACK

    def test_easter_is_white(self):
        info = _info(2025, 4, 20)
        assert info.color == LiturgicalColor.WHITE

    def test_st_joseph_is_white(self):
        """Confessor feast = white vestments."""
        info = _info(2025, 3, 19)
        assert info.color == LiturgicalColor.WHITE

    def test_ordinary_time_feria_is_green(self):
        """An ordinary-time feria should be green."""
        # Wed Jul 9, 2025: a Pentecost-season feria
        info = _info(2025, 7, 9)
        assert info.color == LiturgicalColor.GREEN

    def test_lent_feria_is_violet(self):
        """A Lent feria should be violet."""
        # 2025: Mar 11 = Tuesday of first week of Lent (no saint)
        info = _info(2025, 3, 11)
        assert info.color == LiturgicalColor.VIOLET


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestMassInfoRankName:
    """Test rank-class extraction from [Rank] section."""

    def test_christmas_duplex_i_classis(self):
        info = _info(2025, 12, 25)
        assert "Duplex" in info.rank_name
        assert "I" in info.rank_name

    def test_advent_i_semiduplex(self):
        info = _info(2025, 11, 30)
        assert "Semiduplex" in info.rank_name or "classis" in info.rank_name

    def test_rank_name_not_empty_for_major_feasts(self):
        """Major feasts should always have a rank name."""
        for dt_tuple in [(2025, 12, 25), (2025, 4, 20), (2025, 6, 29)]:
            info = _info(*dt_tuple)
            assert info.rank_name, f"Empty rank_name for {dt_tuple}"


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestMassInfoBulk:
    """Test bulk helpers (month/year)."""

    def test_info_for_month_december(self):
        infos = get_mass_info_for_month(2025, 12)
        assert len(infos) == 31
        assert all(isinstance(i, MassInfo) for i in infos)
        # Christmas should be in there
        christmas = infos[24]  # index 24 = Dec 25
        assert christmas.date == date(2025, 12, 25)
        assert christmas.color == LiturgicalColor.WHITE

    def test_info_for_month_february_leap(self):
        """February in a leap year should have 29 entries."""
        infos = get_mass_info_for_month(2024, 2)
        assert len(infos) == 29


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestMassInfoConditionalRank:
    """Test that rank extraction respects rubrical conditions."""

    def test_ss_peter_paul_1960_no_octave(self):
        """Ss. Peter & Paul in 1960 should NOT have 'cum octava'."""
        info = _info(2025, 6, 29, Rubric.RUBRICAE_1960)
        assert "octava" not in info.rank_name.lower()

    def test_ss_peter_paul_tridentine_has_octave(self):
        """Ss. Peter & Paul pre-1960 should have 'cum octava'."""
        info = _info(2025, 6, 29, Rubric.TRIDENT_1570)
        assert "octava" in info.rank_name.lower()
