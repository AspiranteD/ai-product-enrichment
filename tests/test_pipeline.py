"""Tests for the four-stage enrichment pipeline."""
import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from src.enrichment.pipeline import (
    EnrichmentPipeline,
    EnrichmentResult,
    PipelineConfig,
    enrich_item,
)


def _make_item(**kwargs):
    """Create a mock item with sensible defaults."""
    defaults = {
        "id": "TEST-001",
        "asin": "B0BX2K9GQ6",
        "amazon_description": "Sony WH-1000XM5 Wireless Headphones",
        "amazon_features": "30h battery, Bluetooth 5.2",
        "amazon_department": "Electronics",
        "amazon_category": "Headphones",
        "amazon_subcategory": "",
        "image_urls": None,
        "scraped_price": None,
        "scraping_attempts": 0,
        "scraping_needs_manual": False,
        "wallapop_category": None,
        "wallapop_title": None,
        "wallapop_description": None,
        "keywords": None,
        "short_description": None,
        "related_keywords": None,
        "hashtags": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestEnrichmentResult:
    """Tests for the result data class."""

    def test_success_when_all_ok(self):
        r = EnrichmentResult(lpn="X")
        r.scraping = "ok"
        r.categorization = "ok"
        r.description = "ok"
        assert r.success is True

    def test_success_when_skipped(self):
        r = EnrichmentResult(lpn="X")
        r.scraping = "skipped"
        r.categorization = "ok"
        r.description = "skipped"
        assert r.success is True

    def test_failure_when_errors(self):
        r = EnrichmentResult(lpn="X")
        r.errors.append("Something broke")
        r.scraping = "failed"
        assert r.success is False

    def test_to_dict_contains_all_fields(self):
        r = EnrichmentResult(lpn="X")
        d = r.to_dict()
        assert "lpn" in d
        assert "scraping" in d
        assert "categorization" in d
        assert "description" in d
        assert "listing_updated" in d
        assert "errors" in d
        assert "success" in d


class TestScrapingStage:
    """Stage 1: External data fetching."""

    def test_skip_without_asin(self):
        item = _make_item(asin="")
        pipeline = EnrichmentPipeline(PipelineConfig(scrape_fn=lambda x: None))
        result = EnrichmentResult(lpn="X")
        pipeline._step_scraping(item, result)
        assert result.scraping == "skipped"

    def test_skip_max_attempts(self):
        item = _make_item(scraping_attempts=5)
        pipeline = EnrichmentPipeline(PipelineConfig(max_scraping_attempts=5))
        result = EnrichmentResult(lpn="X")
        pipeline._step_scraping(item, result)
        assert result.scraping == "max_attempts"

    def test_skip_all_data_present(self):
        item = _make_item(
            amazon_description="desc",
            image_urls="img.jpg",
            amazon_features="features",
            scraped_price=29.99,
        )
        pipeline = EnrichmentPipeline(PipelineConfig(scrape_fn=lambda x: {}))
        result = EnrichmentResult(lpn="X")
        pipeline._step_scraping(item, result)
        assert result.scraping == "skipped"

    def test_scrape_ok(self):
        def mock_scrape(sku):
            return {"title": "Product", "images": "img.jpg", "features": "f", "price": 10.0}

        item = _make_item(amazon_description=None, image_urls=None, amazon_features=None)
        pipeline = EnrichmentPipeline(PipelineConfig(scrape_fn=mock_scrape))
        result = EnrichmentResult(lpn="X")
        pipeline._step_scraping(item, result)
        assert result.scraping == "ok"
        assert item.amazon_description == "Product"
        assert item.scraped_price == 10.0

    def test_scrape_none_increments_attempts(self):
        item = _make_item(scraping_attempts=2)
        pipeline = EnrichmentPipeline(PipelineConfig(scrape_fn=lambda x: None))
        result = EnrichmentResult(lpn="X")
        pipeline._step_scraping(item, result)
        assert result.scraping == "failed"
        assert item.scraping_attempts == 3

    def test_scrape_max_marks_manual(self):
        item = _make_item(scraping_attempts=4)
        pipeline = EnrichmentPipeline(PipelineConfig(scrape_fn=lambda x: None, max_scraping_attempts=5))
        result = EnrichmentResult(lpn="X")
        pipeline._step_scraping(item, result)
        assert item.scraping_needs_manual is True

    def test_scrape_no_fn_skips(self):
        item = _make_item()
        pipeline = EnrichmentPipeline(PipelineConfig(scrape_fn=None))
        result = EnrichmentResult(lpn="X")
        pipeline._step_scraping(item, result)
        assert result.scraping == "skipped"

    def test_scrape_exception(self):
        def boom(sku):
            raise ConnectionError("timeout")

        item = _make_item()
        pipeline = EnrichmentPipeline(PipelineConfig(scrape_fn=boom))
        result = EnrichmentResult(lpn="X")
        pipeline._step_scraping(item, result)
        assert result.scraping == "failed"
        assert any("timeout" in e for e in result.errors)


class TestCategorizationStage:
    """Stage 2: Three-tier categorization."""

    @patch("src.enrichment.pipeline.CategoryMapper")
    def test_skip_already_categorized(self, MockMapper):
        item = _make_item(wallapop_category="Tecnología")
        pipeline = EnrichmentPipeline()
        result = EnrichmentResult(lpn="X")
        pipeline._step_categorization(item, result)
        assert result.categorization == "skipped"

    @patch("src.enrichment.pipeline.CategoryMapper")
    def test_no_data_skip(self, MockMapper):
        item = _make_item(amazon_department="", amazon_category="", amazon_description="")
        pipeline = EnrichmentPipeline()
        result = EnrichmentResult(lpn="X")
        pipeline._step_categorization(item, result)
        assert result.categorization == "no_data"

    def test_categorization_ok(self):
        item = _make_item()
        mock_mapper = MagicMock()
        mock_mapper.classify.return_value = "Tecnología y electrónica > Audio"

        pipeline = EnrichmentPipeline()
        pipeline._mapper = mock_mapper
        result = EnrichmentResult(lpn="X")
        pipeline._step_categorization(item, result)

        assert result.categorization == "ok"
        assert item.wallapop_category == "Tecnología y electrónica > Audio"

    def test_categorization_empty_fails(self):
        item = _make_item()
        mock_mapper = MagicMock()
        mock_mapper.classify.return_value = ""

        pipeline = EnrichmentPipeline()
        pipeline._mapper = mock_mapper
        result = EnrichmentResult(lpn="X")
        pipeline._step_categorization(item, result)

        assert result.categorization == "failed"


class TestDescriptionStage:
    """Stage 3: AI content generation."""

    def test_skip_no_description(self):
        item = _make_item(amazon_description="")
        pipeline = EnrichmentPipeline()
        result = EnrichmentResult(lpn="X")
        pipeline._step_description(item, result)
        assert result.description == "no_data"

    def test_skip_all_fields_populated(self):
        item = _make_item(
            wallapop_title="T",
            wallapop_description="D",
            keywords="K",
            short_description="S",
            related_keywords="R",
            hashtags="H",
        )
        pipeline = EnrichmentPipeline()
        result = EnrichmentResult(lpn="X")
        pipeline._step_description(item, result)
        assert result.description == "skipped"

    @patch("src.enrichment.pipeline.generate_listing_content")
    def test_description_ok(self, mock_gen):
        mock_gen.return_value = {
            "titulo_wallapop": "Sony auriculares BT",
            "descripcion_mejorada": "Auriculares premium",
            "palabras_clave": "audio,sony",
            "descripcion_5palabras": "Cascos bluetooth sony",
            "palabras_clave_relacionadas": "music,wireless",
            "hashtags": "#sony,#telovendo",
            "marca": "Sony",
            "modelo": "WH-1000XM5",
            "color": "",
        }
        item = _make_item()
        pipeline = EnrichmentPipeline()
        result = EnrichmentResult(lpn="X")
        pipeline._step_description(item, result)

        assert result.description == "ok"
        assert item.wallapop_title == "Sony auriculares BT"

    @patch("src.enrichment.pipeline.generate_listing_content")
    def test_description_ai_failure(self, mock_gen):
        mock_gen.return_value = None
        item = _make_item()
        pipeline = EnrichmentPipeline()
        result = EnrichmentResult(lpn="X")
        pipeline._step_description(item, result)
        assert result.description == "failed"

    @patch("src.enrichment.pipeline.generate_listing_content")
    def test_existing_titles_queried(self, mock_gen):
        mock_gen.return_value = {"titulo_wallapop": "Title", "descripcion_mejorada": "D"}

        def get_titles(sku, item):
            return ["Existing title 1", "Existing title 2"]

        item = _make_item()
        config = PipelineConfig(get_existing_titles_fn=get_titles)
        pipeline = EnrichmentPipeline(config)
        result = EnrichmentResult(lpn="X")
        pipeline._step_description(item, result)

        call_kwargs = mock_gen.call_args
        assert call_kwargs[1]["existing_titles"] == ["Existing title 1", "Existing title 2"]


class TestListingUpdateStage:
    """Stage 4: Listing propagation."""

    def test_skip_no_content(self):
        item = _make_item(wallapop_title="", wallapop_description="")
        pipeline = EnrichmentPipeline()
        result = EnrichmentResult(lpn="X")
        pipeline._step_update_listing(item, result)
        assert result.listing_updated is False

    def test_listing_updated(self):
        updates = []

        def mock_update(item, title, desc):
            updates.append((title, desc))

        item = _make_item(wallapop_title="Title", wallapop_description="Desc")
        config = PipelineConfig(update_listing_fn=mock_update)
        pipeline = EnrichmentPipeline(config)
        result = EnrichmentResult(lpn="X")
        pipeline._step_update_listing(item, result)

        assert result.listing_updated is True
        assert updates[0] == ("Title", "Desc")


class TestConvenienceWrapper:
    """Tests for the enrich_item() shortcut."""

    @patch("src.enrichment.pipeline.generate_listing_content")
    @patch("src.enrichment.pipeline.CategoryMapper")
    def test_enrich_item_returns_dict(self, MockMapper, mock_gen):
        MockMapper.return_value.classify.return_value = "Cat"
        mock_gen.return_value = {"titulo_wallapop": "T", "descripcion_mejorada": "D"}

        item = _make_item()
        result = enrich_item(item, item_id="TEST")

        assert isinstance(result, dict)
        assert "lpn" in result
        assert "success" in result
