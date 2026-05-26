"""
CLI: Batch AI description generation.

Queries items with source data but missing enrichment fields,
generates marketplace-optimized content via OpenAI, and updates records.

Features:
- Title deduplication: queries existing titles per SKU to prevent duplicates
- Batch commits every 10 items to avoid long transactions
- Configurable delay between API calls (default 1.5s)
- Dry-run mode to preview pending items without modifications
- Progress logging with field-level detail

Usage:
    python -m src.cli.generate_descriptions
    python -m src.cli.generate_descriptions --limit 50
    python -m src.cli.generate_descriptions --dry-run
    python -m src.cli.generate_descriptions --delay 2.0
"""
import argparse
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.enrichment.description_generator import generate_listing_content
from src.enrichment.listing_builder import apply_enrichment, ENRICHMENT_FIELDS

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Configuration for batch description generation."""
    limit: int | None = None
    dry_run: bool = False
    delay: float = 1.5
    commit_batch_size: int = 10


@dataclass
class BatchStats:
    """Statistics from a batch run."""
    total: int = 0
    ok: int = 0
    failed: int = 0
    skipped: int = 0

    def summary(self) -> str:
        return f"{self.ok} OK / {self.failed} FAIL / {self.skipped} SKIP / {self.total} total"


def run_batch(
    items: list[Any],
    config: BatchConfig,
    get_existing_titles_fn: Optional[Callable] = None,
    commit_fn: Optional[Callable] = None,
) -> BatchStats:
    """
    Process a batch of items for description generation.

    Args:
        items: List of item objects to enrich.
        config: Batch configuration.
        get_existing_titles_fn: Callable(sku, item) -> list[str] for title dedup.
        commit_fn: Callable(batch_count) to persist changes. Called every
            commit_batch_size items.

    Returns:
        BatchStats with totals.
    """
    stats = BatchStats(total=len(items))

    if config.dry_run:
        for i, item in enumerate(items, 1):
            missing = [f for f in ENRICHMENT_FIELDS if not getattr(item, f, None)]
            desc = (getattr(item, "amazon_description", "") or "")[:50]
            item_id = getattr(item, "id", getattr(item, "lpn", f"item-{i}"))
            logger.info(
                "  [%d] ID=%s desc='%s...' missing=%s",
                i, item_id, desc, missing,
            )
        logger.info("DRY RUN — no changes made")
        return stats

    batch_count = 0

    for i, item in enumerate(items, 1):
        desc = (getattr(item, "amazon_description", "") or "").strip()
        features = (getattr(item, "amazon_features", "") or "").strip()
        asin = (getattr(item, "asin", "") or "").strip()
        item_id = getattr(item, "id", getattr(item, "lpn", f"item-{i}"))

        logger.info("[%d/%d] ID=%s - '%s...'", i, stats.total, item_id, desc[:60])

        existing_titles: list[str] = []
        if asin and get_existing_titles_fn:
            existing_titles = get_existing_titles_fn(asin, item)

        enrichment = generate_listing_content(
            desc, features, sku=asin,
            existing_titles=existing_titles or None,
        )

        if not enrichment:
            logger.warning("  No content generated for %s", item_id)
            stats.failed += 1
            continue

        updated = apply_enrichment(item, enrichment)
        if updated:
            batch_count += 1
            stats.ok += 1
            logger.info("  title: '%s'", enrichment.get("titulo_wallapop", ""))
            logger.info("  brand: %s | model: %s", enrichment.get("marca", ""), enrichment.get("modelo", ""))
        else:
            stats.skipped += 1
            logger.info("  No new fields for %s", item_id)

        if batch_count >= config.commit_batch_size and commit_fn:
            commit_fn(batch_count)
            logger.info("  Batch of %d committed", batch_count)
            batch_count = 0

        if i < stats.total:
            time.sleep(config.delay)

    if batch_count > 0 and commit_fn:
        commit_fn(batch_count)
        logger.info("  Final batch of %d committed", batch_count)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Batch AI description generation")
    parser.add_argument("--limit", type=int, default=None, help="Max items to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview pending items only")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between OpenAI calls (default: 1.5)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    config = BatchConfig(limit=args.limit, dry_run=args.dry_run, delay=args.delay)

    logger.info("=" * 60)
    logger.info("DESCRIPTION GENERATION - Start")
    logger.info("Limit: %s | Delay: %.1fs", config.limit or "none", config.delay)
    logger.info("=" * 60)

    # In production, items come from a database query.
    # This CLI demonstrates the batch processing pattern.
    logger.info("Connect to your data source and call run_batch(items, config, ...)")
    logger.info("See examples/enrich_single_item.py for a complete integration example.")


if __name__ == "__main__":
    main()
