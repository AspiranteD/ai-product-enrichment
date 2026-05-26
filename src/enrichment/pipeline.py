"""
Product enrichment pipeline orchestrator.

Chains multiple enrichment steps in sequence:
  1. Product data scraping (external)
  2. AI-powered categorization
  3. AI-powered description generation
  4. Listing assembly with policy sanitization

Each step is idempotent: only writes empty fields, never overwrites existing data.
Designed to be invoked from a command queue, scheduler, or directly.
"""
import logging
import time
from typing import Optional, Any, Protocol

logger = logging.getLogger(__name__)

DELAY_BETWEEN_STEPS_SECONDS = 2.0


class ProductData(Protocol):
    """Protocol for product data objects (works with ORM models, dicts, dataclasses)."""
    product_id: str
    source_description: Optional[str]
    source_features: Optional[str]
    source_department: Optional[str]
    source_category: Optional[str]
    source_subcategory: Optional[str]
    marketplace_category: Optional[str]
    marketplace_title: Optional[str]
    marketplace_description: Optional[str]
    keywords: Optional[str]
    short_description: Optional[str]
    related_keywords: Optional[str]
    hashtags: Optional[str]
    brand: Optional[str]
    model: Optional[str]
    color: Optional[str]


class EnrichmentResult:
    """Detailed result of the enrichment pipeline."""

    def __init__(self, product_id: str):
        self.product_id = product_id
        self.categorization: Optional[str] = None
        self.description: Optional[str] = None
        self.listing_updated: bool = False
        self.errors: list[str] = []

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "categorization": self.categorization,
            "description": self.description,
            "listing_updated": self.listing_updated,
            "errors": self.errors,
            "success": not self.errors or all(
                s in ("ok", "skipped") for s in
                [self.categorization, self.description]
                if s is not None
            ),
        }


def enrich_item(
    product: Any,
    save_fn: Optional[callable] = None,
    existing_titles: list[str] | None = None,
) -> dict:
    """
    Run the full enrichment pipeline on a product.

    Args:
        product: Object with product_id, source_description, source_department,
                 marketplace_category, marketplace_title, etc.
        save_fn: Optional callback to persist changes (called after each step).
        existing_titles: Titles already used by similar products (for dedup).

    Returns:
        Dict with detailed results for each pipeline step.
    """
    pid = getattr(product, "product_id", "unknown")
    result = EnrichmentResult(pid)
    logger.info("Enrichment START: %s", pid)

    _step_categorization(product, result)

    if result.categorization == "ok":
        time.sleep(DELAY_BETWEEN_STEPS_SECONDS)

    if save_fn:
        save_fn(product)

    _step_description(product, result, existing_titles)

    if save_fn:
        save_fn(product)

    logger.info(
        "Enrichment DONE: %s | categorization=%s description=%s",
        pid, result.categorization, result.description,
    )
    return result.to_dict()


def _step_categorization(product: Any, result: EnrichmentResult):
    """Step 1: Classify into marketplace categories."""
    current_cat = getattr(product, "marketplace_category", None)
    if current_cat and str(current_cat).strip():
        result.categorization = "skipped"
        logger.info("  Categorization SKIP: %s already has '%s'", product.product_id, current_cat)
        return

    dept = (getattr(product, "source_department", None) or "").strip()
    cat = (getattr(product, "source_category", None) or "").strip()
    desc = (getattr(product, "source_description", None) or "").strip()

    if not dept and not cat and not desc:
        result.categorization = "no_data"
        logger.info("  Categorization SKIP: %s has no department/category/description", product.product_id)
        return

    try:
        from .category_mapper import CategoryMapper

        mapper = CategoryMapper()
        category = mapper.classify(
            department=dept,
            category=cat,
            subcategory=(getattr(product, "source_subcategory", None) or "").strip(),
            description=desc,
            features=(getattr(product, "source_features", None) or "").strip(),
            use_ai=True,
        )

        if category and category.strip():
            product.marketplace_category = category
            result.categorization = "ok"
            logger.info("  Categorization OK: %s -> '%s'", product.product_id, category)
        else:
            result.categorization = "failed"
            result.errors.append("Categorization returned empty")
            logger.warning("  Categorization FAIL: %s empty result", product.product_id)

    except Exception as e:
        result.categorization = "failed"
        result.errors.append(f"Categorization error: {e}")
        logger.error("  Categorization ERROR: %s - %s", product.product_id, e)


def _step_description(
    product: Any,
    result: EnrichmentResult,
    existing_titles: list[str] | None = None,
):
    """Step 2: Generate enriched description with AI."""
    desc = (getattr(product, "source_description", None) or "").strip()
    if not desc:
        result.description = "no_data"
        logger.info("  Description SKIP: %s has no source description", product.product_id)
        return

    already_has = all([
        getattr(product, "marketplace_title", None),
        getattr(product, "marketplace_description", None),
        getattr(product, "keywords", None),
        getattr(product, "short_description", None),
        getattr(product, "related_keywords", None),
        getattr(product, "hashtags", None),
    ])
    if already_has:
        result.description = "skipped"
        logger.info("  Description SKIP: %s already has all fields", product.product_id)
        return

    try:
        from .description_generator import generate_listing_content

        features = (getattr(product, "source_features", None) or "").strip()
        content = generate_listing_content(
            desc, features,
            product_id=product.product_id,
            existing_titles=existing_titles,
        )

        if not content:
            result.description = "failed"
            result.errors.append("AI returned no content")
            logger.warning("  Description FAIL: %s AI returned None", product.product_id)
            return

        field_map = {
            "keywords": "keywords",
            "short_description": "short_description",
            "listing_title": "marketplace_title",
            "enhanced_description": "marketplace_description",
            "related_keywords": "related_keywords",
            "brand": "brand",
            "model": "model",
            "color": "color",
            "hashtags": "hashtags",
        }

        updated = False
        for src_key, dest_attr in field_map.items():
            value = content.get(src_key, "")
            if value and not getattr(product, dest_attr, None):
                setattr(product, dest_attr, value)
                updated = True

        if updated:
            result.description = "ok"
            logger.info("  Description OK: %s title='%s'", product.product_id, content.get("listing_title", ""))
        else:
            result.description = "skipped"
            logger.info("  Description SKIP: %s no new fields to write", product.product_id)

    except Exception as e:
        result.description = "failed"
        result.errors.append(f"Description error: {e}")
        logger.error("  Description ERROR: %s - %s", product.product_id, e)
