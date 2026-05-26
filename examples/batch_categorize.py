"""
Example: Batch categorize products with statistics tracking.

Demonstrates:
1. Direct mapping (80%+ of items — free, instant)
2. AI classification fallback
3. Department-level fallback
4. Per-method statistics
5. Batch commit pattern
"""
import logging
from types import SimpleNamespace

from src.enrichment.category_mapper import CategoryMapper
from src.cli.categorize_items import run_batch, BatchConfig, CategorizationStats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    items = [
        SimpleNamespace(
            id="ITEM-001",
            amazon_department="Electronics",
            amazon_category="Headphones",
            amazon_subcategory="Over-Ear",
            amazon_description="Sony WH-1000XM5 Noise Cancelling Headphones",
            amazon_features="30h battery, Bluetooth 5.2",
            wallapop_category=None,
        ),
        SimpleNamespace(
            id="ITEM-002",
            amazon_department="Home Improvement",
            amazon_category="Power Tools",
            amazon_subcategory="Drills",
            amazon_description="Bosch Professional GSR 18V-60 FC Cordless Drill",
            amazon_features="18V, 60Nm torque, FlexiClick system",
            wallapop_category=None,
        ),
        SimpleNamespace(
            id="ITEM-003",
            amazon_department="Pet Products",
            amazon_category="Dogs",
            amazon_subcategory="Beds",
            amazon_description="Orthopedic Dog Bed Large",
            amazon_features="Memory foam, washable cover",
            wallapop_category=None,
        ),
        SimpleNamespace(
            id="ITEM-004",
            amazon_department="NewDepartment",
            amazon_category="UnknownCategory",
            amazon_subcategory="",
            amazon_description="Some mysterious product from a new department",
            amazon_features="",
            wallapop_category=None,
        ),
    ]

    config = BatchConfig(use_ai=False)  # AI disabled for demo — uses mapping + fallback

    committed = []

    def commit(batch_size):
        committed.append(batch_size)

    stats = run_batch(items, config, commit_fn=commit)

    print("\n" + "=" * 60)
    print("CATEGORIZATION RESULTS:")
    print(stats.summary())
    print(f"\nCommit calls: {committed}")

    print("\nITEM CATEGORIES:")
    for item in items:
        print(f"  {item.id}: {item.wallapop_category}")


if __name__ == "__main__":
    main()
