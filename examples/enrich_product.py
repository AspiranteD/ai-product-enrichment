#!/usr/bin/env python3
"""
Example: Enrich a single product using the AI pipeline.

Usage:
    export OPENAI_API_KEY=sk-...
    python examples/enrich_product.py
"""
import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.enrichment import (
    enrich_item,
    CategoryMapper,
    generate_listing_content,
    build_listing_title,
    build_listing_description,
)


def main():
    # 1. Create a product (could come from your database, CSV, API, etc.)
    product = SimpleNamespace(
        product_id="B08N5WRWNW",
        source_description="Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black",
        source_features="Industry Leading Noise Cancellation; Dual Noise Sensor Technology; Up to 30-hour battery life; Touch Sensor controls; Speak-to-Chat technology",
        source_department="Electronics",
        source_category="Headphones",
        source_subcategory="Over-Ear",
        marketplace_category=None,
        marketplace_title=None,
        marketplace_description=None,
        keywords=None,
        short_description=None,
        related_keywords=None,
        hashtags=None,
        brand=None,
        model=None,
        color=None,
    )

    print("=" * 60)
    print("AI Product Enrichment - Example")
    print("=" * 60)
    print(f"\nInput: {product.source_description[:80]}...")

    # 2. Run the full enrichment pipeline
    result = enrich_item(product)

    # 3. Display results
    print(f"\nPipeline result:")
    print(f"  Categorization: {result['categorization']}")
    print(f"  Description:    {result['description']}")
    print(f"  Success:        {result['success']}")

    if product.marketplace_category:
        print(f"\nCategory: {product.marketplace_category}")
    if product.marketplace_title:
        print(f"Title:    {product.marketplace_title}")
    if product.brand:
        print(f"Brand:    {product.brand}")
    if product.model:
        print(f"Model:    {product.model}")
    if product.keywords:
        print(f"Keywords: {product.keywords}")

    # 4. Build the formatted listing
    title = build_listing_title(
        enriched_title=product.marketplace_title or "",
        condition_code="PERFECT",
    )
    description = build_listing_description(
        item_id=product.product_id,
        condition_code="PERFECT",
        brand=product.brand or "",
        model=product.model or "",
        color=product.color or "",
        enriched_description=product.marketplace_description or "",
        keywords=product.keywords or "",
        related_keywords=product.related_keywords or "",
        short_description=product.short_description or "",
    )

    print(f"\n{'=' * 60}")
    print("FORMATTED LISTING")
    print(f"{'=' * 60}")
    print(f"\nTitle: {title}")
    print(f"\nDescription:\n{description}")


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY environment variable first")
        print("  export OPENAI_API_KEY=sk-...")
        sys.exit(1)
    main()
