"""
Example: Enrich a single product through the full pipeline.

Demonstrates:
1. Pluggable scraping function (simulated here)
2. Three-tier categorization (mapping → AI → fallback)
3. AI description generation with title deduplication
4. Listing update propagation
5. Detailed per-stage result tracking
"""
import logging
from types import SimpleNamespace

from src.enrichment.pipeline import EnrichmentPipeline, PipelineConfig
from src.enrichment.policy_sanitizer import sanitize_text, has_risk_word

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def simulate_scrape(sku: str) -> dict | None:
    """Simulated scraper — replace with real HTTP scraping in production."""
    catalog = {
        "B0BX2K9GQ6": {
            "title": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
            "images": "https://example.com/sony-xm5-1.jpg;https://example.com/sony-xm5-2.jpg",
            "features": "30-hour battery life\nBluetooth 5.2\nMultipoint connection\nSpeak-to-Chat",
            "price": 349.99,
        },
        "B09V3KXJPB": {
            "title": "Dreame L10s Ultra Robot Vacuum and Mop",
            "images": "https://example.com/dreame-1.jpg",
            "features": "5300Pa suction\nAuto mop washing\nHot air drying\nLiDAR navigation",
            "price": 899.00,
        },
    }
    return catalog.get(sku)


def get_existing_titles(sku: str, item) -> list[str]:
    """Simulated title lookup — replace with DB query in production."""
    known = {
        "B0BX2K9GQ6": [
            "Sony WH-1000XM5 auriculares bluetooth",
            "Cascos Sony cancelación ruido WH-1000XM5",
        ],
    }
    return known.get(sku, [])


def update_listing(item, title: str, description: str):
    """Simulated listing update — replace with DB write in production."""
    print(f"  → Listing updated: title='{title}' desc='{description[:60]}...'")


def main():
    item = SimpleNamespace(
        id="LPN-00123",
        sku="B0BX2K9GQ6",
        source_description=None,
        source_features=None,
        source_department="Electronics",
        source_category="Headphones",
        source_subcategory="Over-Ear",
        image_urls=None,
        scraped_price=None,
        scraping_attempts=0,
        scraping_needs_manual=False,
        marketplace_category=None,
        wallapop_title=None,
        wallapop_description=None,
        keywords=None,
        short_description=None,
        related_keywords=None,
        hashtags=None,
        brand=None,
        model=None,
        color=None,
    )

    config = PipelineConfig(
        delay_between_steps=0.5,
        max_scraping_attempts=5,
        use_ai_categorization=True,
        scrape_fn=simulate_scrape,
        get_existing_titles_fn=get_existing_titles,
        update_listing_fn=update_listing,
    )

    pipeline = EnrichmentPipeline(config)
    result = pipeline.enrich(item, item_id=item.id)

    print("\n" + "=" * 60)
    print("ENRICHMENT RESULT:")
    for key, value in result.to_dict().items():
        print(f"  {key}: {value}")

    print("\nENRICHED ITEM:")
    print(f"  Category:    {item.marketplace_category}")
    print(f"  Title:       {item.wallapop_title}")
    print(f"  Description: {item.wallapop_description}")
    print(f"  Keywords:    {item.keywords}")
    print(f"  Brand:       {item.brand}")
    print(f"  Model:       {item.model}")

    # Policy check
    if has_risk_word(item.wallapop_title, item.wallapop_description):
        print("\n⚠ Title/description contain policy-sensitive terms!")
        print(f"  Sanitized title: {sanitize_text(item.wallapop_title, for_title=True)}")
        print(f"  Sanitized desc:  {sanitize_text(item.wallapop_description)}")
    else:
        print("\n✓ No policy-sensitive terms detected")


if __name__ == "__main__":
    main()
