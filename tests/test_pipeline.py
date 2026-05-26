"""Tests for the enrichment pipeline orchestrator."""
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from src.enrichment.pipeline import enrich_item, EnrichmentResult, _step_categorization, _step_description


def _make_product(**overrides):
    """Create a mock product with sensible defaults."""
    defaults = {
        "product_id": "PROD-001",
        "source_description": None,
        "source_features": None,
        "source_department": None,
        "source_category": None,
        "source_subcategory": None,
        "marketplace_category": None,
        "marketplace_title": None,
        "marketplace_description": None,
        "keywords": None,
        "short_description": None,
        "related_keywords": None,
        "hashtags": None,
        "brand": None,
        "model": None,
        "color": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestEnrichmentResult:

    def test_to_dict_structure(self):
        r = EnrichmentResult("TEST-123")
        d = r.to_dict()
        assert d["product_id"] == "TEST-123"
        assert "categorization" in d
        assert "description" in d
        assert "errors" in d
        assert "success" in d

    def test_success_when_all_ok(self):
        r = EnrichmentResult("TEST")
        r.categorization = "ok"
        r.description = "ok"
        assert r.to_dict()["success"] is True

    def test_success_when_all_skipped(self):
        r = EnrichmentResult("TEST")
        r.categorization = "skipped"
        r.description = "skipped"
        assert r.to_dict()["success"] is True

    def test_failure_reported(self):
        r = EnrichmentResult("TEST")
        r.categorization = "failed"
        r.errors.append("something broke")
        d = r.to_dict()
        assert len(d["errors"]) > 0


class TestStepCategorization:

    def test_skip_if_already_categorized(self):
        product = _make_product(marketplace_category="Technology > Audio")
        result = EnrichmentResult("TEST")
        _step_categorization(product, result)
        assert result.categorization == "skipped"

    def test_no_data_available(self):
        product = _make_product()
        result = EnrichmentResult("TEST")
        _step_categorization(product, result)
        assert result.categorization == "no_data"


class TestStepDescription:

    def test_skip_no_source_description(self):
        product = _make_product()
        result = EnrichmentResult("TEST")
        _step_description(product, result)
        assert result.description == "no_data"

    def test_skip_already_complete(self):
        product = _make_product(
            source_description="Some product",
            marketplace_title="Title",
            marketplace_description="Desc",
            keywords="kw1,kw2",
            short_description="Short",
            related_keywords="rel1",
            hashtags="#tag1",
        )
        result = EnrichmentResult("TEST")
        _step_description(product, result)
        assert result.description == "skipped"

    @patch("src.enrichment.pipeline.generate_listing_content")
    def test_generates_content(self, mock_generate):
        mock_generate.return_value = {
            "listing_title": "Great Widget",
            "enhanced_description": "A wonderful widget",
            "keywords": "widget,tool",
            "short_description": "Useful compact widget tool",
            "related_keywords": "gadget,device",
            "hashtags": "#widget,#tool",
            "brand": "WidgetCo",
            "model": "W-100",
            "color": "Black",
        }
        product = _make_product(source_description="Amazon Widget Description")
        result = EnrichmentResult("TEST")
        _step_description(product, result)

        assert result.description == "ok"
        assert product.marketplace_title == "Great Widget"
        assert product.brand == "WidgetCo"
