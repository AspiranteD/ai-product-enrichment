"""Tests for the listing builder / field mapper."""
import pytest
from types import SimpleNamespace

from src.enrichment.listing_builder import (
    apply_enrichment,
    get_missing_fields,
    is_fully_enriched,
    build_listing_title,
    build_listing_description,
    FIELD_MAP,
    ENRICHMENT_FIELDS,
)


def _make_item(**kwargs):
    defaults = {f: None for f in set(FIELD_MAP.values()) | set(ENRICHMENT_FIELDS)}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestApplyEnrichment:
    """Idempotent field mapping from AI output to item."""

    def test_maps_all_fields(self):
        enrichment = {
            "palabras_clave": "keyword1,keyword2",
            "descripcion_5palabras": "Short five word desc",
            "titulo_wallapop": "Great Product Title",
            "descripcion_mejorada": "Long description here",
            "palabras_clave_relacionadas": "related1,related2",
            "marca": "BrandX",
            "modelo": "Model100",
            "color": "Rojo",
            "hashtags": "#brand,#telovendo",
        }
        item = _make_item()
        updated = apply_enrichment(item, enrichment)

        assert updated is True
        assert item.keywords == "keyword1,keyword2"
        assert item.short_description == "Short five word desc"
        assert item.wallapop_title == "Great Product Title"
        assert item.wallapop_description == "Long description here"
        assert item.brand == "BrandX"
        assert item.model == "Model100"
        assert item.color == "Rojo"

    def test_does_not_overwrite_existing(self):
        enrichment = {
            "titulo_wallapop": "New Title",
            "descripcion_mejorada": "New Description",
        }
        item = _make_item(wallapop_title="Existing Title")
        updated = apply_enrichment(item, enrichment)

        assert updated is True
        assert item.wallapop_title == "Existing Title"  # NOT overwritten
        assert item.wallapop_description == "New Description"

    def test_empty_enrichment_no_update(self):
        item = _make_item(wallapop_title="Has Title")
        updated = apply_enrichment(item, {})
        assert updated is False

    def test_empty_values_not_written(self):
        enrichment = {"titulo_wallapop": "", "marca": ""}
        item = _make_item()
        updated = apply_enrichment(item, enrichment)
        assert updated is False
        assert item.wallapop_title is None


class TestMissingFields:
    """Detection of missing enrichment fields."""

    def test_all_missing(self):
        item = _make_item()
        missing = get_missing_fields(item)
        assert set(missing) == set(ENRICHMENT_FIELDS)

    def test_none_missing(self):
        item = _make_item(
            wallapop_title="T", wallapop_description="D",
            keywords="K", short_description="S",
            related_keywords="R", hashtags="H",
        )
        assert get_missing_fields(item) == []

    def test_partial_missing(self):
        item = _make_item(wallapop_title="T", keywords="K")
        missing = get_missing_fields(item)
        assert "wallapop_title" not in missing
        assert "keywords" not in missing
        assert "wallapop_description" in missing


class TestFullyEnriched:

    def test_fully_enriched(self):
        item = _make_item(
            wallapop_title="T", wallapop_description="D",
            keywords="K", short_description="S",
            related_keywords="R", hashtags="H",
        )
        assert is_fully_enriched(item) is True

    def test_not_fully_enriched(self):
        item = _make_item(wallapop_title="T")
        assert is_fully_enriched(item) is False


class TestBuildHelpers:

    def test_build_title(self):
        item = _make_item(wallapop_title="  Trimmed Title  ")
        assert build_listing_title(item) == "Trimmed Title"

    def test_build_title_none(self):
        item = _make_item(wallapop_title=None)
        assert build_listing_title(item) == ""

    def test_build_description(self):
        item = _make_item(wallapop_description="  Desc  ")
        assert build_listing_description(item) == "Desc"
