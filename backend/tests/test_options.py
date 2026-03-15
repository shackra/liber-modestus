"""Tests for the Mass options module."""

from pathlib import Path

import pytest

from captator.options import (
    MassOptions,
    Option,
    get_languages_from_disk,
    get_mass_options,
)
from captator.resolver.config import MassType, OrderVariant, Rubric

_MISSA = (
    Path(__file__).parent.parent / "src" / "divinum-officium" / "web" / "www" / "missa"
)
_HAS_DATA = _MISSA.is_dir()


class TestGetMassOptions:
    def test_returns_mass_options(self):
        opts = get_mass_options()
        assert isinstance(opts, MassOptions)

    def test_rubrics_are_present(self):
        opts = get_mass_options()
        assert len(opts.rubrics) == 5
        values = {o.value for o in opts.rubrics}
        assert Rubric.RUBRICAE_1960.name in values
        assert Rubric.TRIDENT_1570.name in values

    def test_rubrics_have_labels(self):
        opts = get_mass_options()
        for o in opts.rubrics:
            assert o.label
            assert o.value

    def test_mass_types_are_present(self):
        opts = get_mass_options()
        assert len(opts.mass_types) == 3
        values = {o.value for o in opts.mass_types}
        assert MassType.READ.name in values
        assert MassType.SOLEMN.name in values
        assert MassType.REQUIEM.name in values

    def test_orders_are_present(self):
        opts = get_mass_options()
        assert len(opts.orders) == 4
        values = {o.value for o in opts.orders}
        assert OrderVariant.ROMAN.name in values
        assert OrderVariant.MONASTIC.name in values

    def test_languages_include_latin_and_english(self):
        opts = get_mass_options()
        assert len(opts.languages) >= 10
        values = {o.value for o in opts.languages}
        assert "Latin" in values
        assert "English" in values
        assert "Espanol" in values

    def test_votives_start_with_hodie(self):
        opts = get_mass_options()
        assert opts.votives[0].value == "Hodie"

    def test_votives_include_requiem(self):
        opts = get_mass_options()
        values = {o.value for o in opts.votives}
        assert "C9" in values

    def test_votives_include_coronatio(self):
        opts = get_mass_options()
        values = {o.value for o in opts.votives}
        assert "Coronatio" in values

    def test_communes_include_all_base_communes(self):
        opts = get_mass_options()
        values = {o.value for o in opts.communes}
        for key in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11"):
            assert key in values, f"Missing commune {key}"

    def test_option_fields(self):
        opts = get_mass_options()
        first = opts.rubrics[0]
        assert isinstance(first, Option)
        assert isinstance(first.value, str)
        assert isinstance(first.label, str)
        assert isinstance(first.description, str)

    def test_all_options_are_tuples(self):
        """Options are immutable tuples, not mutable lists."""
        opts = get_mass_options()
        assert isinstance(opts.rubrics, tuple)
        assert isinstance(opts.mass_types, tuple)
        assert isinstance(opts.orders, tuple)
        assert isinstance(opts.languages, tuple)
        assert isinstance(opts.votives, tuple)
        assert isinstance(opts.communes, tuple)

    def test_no_duplicate_values_in_votives(self):
        opts = get_mass_options()
        values = [o.value for o in opts.votives]
        assert len(values) == len(set(values))


@pytest.mark.skipif(not _HAS_DATA, reason="DO submodule not available")
class TestGetLanguagesFromDisk:
    def test_finds_languages(self):
        langs = get_languages_from_disk(_MISSA)
        assert len(langs) >= 10
        values = {o.value for o in langs}
        assert "Latin" in values
        assert "English" in values

    def test_latin_is_first(self):
        langs = get_languages_from_disk(_MISSA)
        assert langs[0].value == "Latin"

    def test_nonexistent_path_returns_empty(self):
        langs = get_languages_from_disk("/nonexistent/path")
        assert langs == ()
