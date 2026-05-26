"""
CLI: Batch product categorization.

Classifies uncategorized items using the three-tier strategy:
1. Direct mapping from JSON (free, instant)
2. AI classification via OpenAI (costs ~$0.001/item)
3. Department fallback (free, always succeeds)

Tracks statistics per classification method to measure mapping coverage
and identify gaps where new mappings should be added.

Usage:
    python -m src.cli.categorize_items
    python -m src.cli.categorize_items --limit 100
    python -m src.cli.categorize_items --dry-run
    python -m src.cli.categorize_items --no-ai
"""
import argparse
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.enrichment.category_mapper import CategoryMapper, DEPARTMENT_FALLBACK

logger = logging.getLogger(__name__)

INVALID_RESPONSES = [
    "no hay descripción",
    "no hay descripcion",
    "por favor, proporciona",
    "no se puede clasificar",
    "no proporcionada",
]


def _is_invalid(value: str | None) -> bool:
    if not value:
        return True
    v = value.strip().lower()
    return any(phrase in v for phrase in INVALID_RESPONSES)


@dataclass
class CategorizationStats:
    """Per-method statistics from a categorization run."""
    total: int = 0
    by_mapping: int = 0
    by_ai: int = 0
    by_fallback: int = 0
    skipped: int = 0

    def summary(self) -> str:
        lines = [f"Total: {self.total}"]
        if self.total > 0:
            lines.append(f"  Mapping: {self.by_mapping} ({self.by_mapping / self.total * 100:.1f}%)")
            lines.append(f"  AI:      {self.by_ai} ({self.by_ai / self.total * 100:.1f}%)")
            lines.append(f"  Fallback:{self.by_fallback} ({self.by_fallback / self.total * 100:.1f}%)")
            lines.append(f"  Skipped: {self.skipped}")
        return "\n".join(lines)


@dataclass
class BatchConfig:
    """Configuration for batch categorization."""
    limit: int | None = None
    dry_run: bool = False
    use_ai: bool = True
    commit_batch_size: int = 10
    delay_between_batches: float = 1.5


def run_batch(
    items: list[Any],
    config: BatchConfig,
    mapper: CategoryMapper | None = None,
    commit_fn: Optional[Callable] = None,
) -> CategorizationStats:
    """
    Categorize a batch of items.

    Args:
        items: List of item objects with source_department, source_category, etc.
        config: Batch configuration.
        mapper: CategoryMapper instance (created if not provided).
        commit_fn: Callable(batch_count) for persistence.

    Returns:
        CategorizationStats with per-method breakdown.
    """
    mapper = mapper or CategoryMapper()
    stats = CategorizationStats(total=len(items))

    if config.dry_run:
        for i, item in enumerate(items, 1):
            dept = getattr(item, "source_department", "") or ""
            cat = getattr(item, "source_category", "") or ""
            desc = (getattr(item, "source_description", "") or "")[:50]
            item_id = getattr(item, "id", f"item-{i}")
            logger.info(
                "  [%d] ID=%s dept='%s' cat='%s' desc='%s...'",
                i, item_id, dept, cat, desc,
            )
        logger.info("DRY RUN — no changes made")
        return stats

    batch_count = 0
    for i, item in enumerate(items, 1):
        dept = (getattr(item, "source_department", "") or "").strip()
        cat = (getattr(item, "source_category", "") or "").strip()
        subcat = (getattr(item, "source_subcategory", "") or "").strip()
        desc = (getattr(item, "source_description", "") or "").strip()
        features = (getattr(item, "source_features", "") or "").strip()
        item_id = getattr(item, "id", f"item-{i}")

        logger.info("[%d/%d] ID=%s dept='%s' cat='%s'", i, stats.total, item_id, dept[:30], cat[:30])

        category = mapper.classify(
            department=dept,
            category=cat,
            subcategory=subcat,
            description=desc,
            features=features,
            use_ai=config.use_ai,
        )

        if _is_invalid(category):
            logger.warning("  Invalid response: '%s' — not saved", category)
            stats.skipped += 1
            continue

        mapped = mapper.get_mapped_category(dept, cat)
        if mapped:
            stats.by_mapping += 1
        elif category == DEPARTMENT_FALLBACK.get(dept, DEPARTMENT_FALLBACK.get("", "")):
            stats.by_fallback += 1
        else:
            stats.by_ai += 1

        item.marketplace_category = category
        batch_count += 1
        logger.info("  -> %s", category)

        if batch_count >= config.commit_batch_size:
            if commit_fn:
                commit_fn(batch_count)
            logger.info("  Batch of %d committed", batch_count)
            batch_count = 0
            time.sleep(config.delay_between_batches)

    if batch_count > 0 and commit_fn:
        commit_fn(batch_count)
        logger.info("  Final batch of %d committed", batch_count)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Batch product categorization")
    parser.add_argument("--limit", type=int, default=None, help="Max items to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview pending items only")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI, use mapping + fallback only")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    config = BatchConfig(limit=args.limit, dry_run=args.dry_run, use_ai=not args.no_ai)

    logger.info("=" * 60)
    logger.info("CATEGORIZATION - Start")
    logger.info("AI: %s | Limit: %s", "disabled" if not config.use_ai else "enabled", config.limit or "none")
    logger.info("=" * 60)

    logger.info("Connect to your data source and call run_batch(items, config, ...)")
    logger.info("See examples/batch_categorize.py for a complete integration example.")


if __name__ == "__main__":
    main()
