"""Tests for the listing title and description builder."""
from src.enrichment.listing_builder import build_listing_title, build_listing_description


class TestBuildListingTitle:

    def test_perfect_condition(self):
        title = build_listing_title(enriched_title="Sony WH-1000XM5 Headphones")
        assert "Sony" in title
        assert len(title) <= 50

    def test_damaged_condition_prefix(self):
        title = build_listing_title(enriched_title="Sony WH-1000XM5", condition_code="DAMAGED")
        assert title.startswith("💰")

    def test_for_parts_condition_prefix(self):
        title = build_listing_title(enriched_title="Sony WH-1000XM5", condition_code="FOR_PARTS")
        assert title.startswith("💔")

    def test_fallback_to_source_description(self):
        title = build_listing_title(source_description="Wireless headphones noise cancelling")
        assert len(title) > 0

    def test_empty_returns_empty(self):
        assert build_listing_title() == ""


class TestBuildListingDescription:

    def test_full_description_assembly(self):
        desc = build_listing_description(
            item_id="ITEM-001",
            condition_code="PERFECT",
            brand="Sony",
            model="WH-1000XM5",
            color="Black",
            enriched_description="Premium noise-cancelling headphones",
            keywords="headphones,sony,wireless",
            related_keywords="audio,music,bluetooth",
            short_description="Wireless noise-cancelling headphones",
        )
        assert "✅" in desc
        assert "Sony" in desc
        assert "WH-1000XM5" in desc
        assert "ITEM-001" in desc
        assert "Keywords" in desc

    def test_damaged_condition(self):
        desc = build_listing_description(
            condition_code="DAMAGED",
            condition_notes="Screen has minor scratches",
            enriched_description="Tablet 10 inch",
        )
        assert "⚠️" in desc
        assert "scratches" in desc

    def test_minimal_fallback(self):
        desc = build_listing_description(
            item_id="ITEM-002",
            source_description="Basic product",
        )
        assert "ITEM-002" in desc

    def test_already_formatted_reused(self):
        existing = "✅ EXCELLENT CONDITION ✅\n\n📝 Already formatted"
        desc = build_listing_description(
            existing_description=existing,
            condition_code="PERFECT",
        )
        assert desc == existing
