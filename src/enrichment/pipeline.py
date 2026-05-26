"""
Four-stage product enrichment pipeline.

Orchestrates the complete flow:
  1. Data scraping (external) — fetch product data if missing
  2. Categorization — three-tier classification
  3. Description generation — AI content creation with title deduplication
  4. Listing update — propagate title/description to linked listings

Each step is idempotent: only writes empty fields, never overwrites existing data.
Steps run sequentially with configurable delays to avoid API rate limits.

The pipeline is designed to be invoked:
- One item at a time from a command poller (real-time enrichment)
- In batch from CLI scripts (bulk processing with progress tracking)
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .category_mapper import CategoryMapper
from .description_generator import generate_listing_content
from .listing_builder import apply_enrichment, build_listing_title, build_listing_description

logger = logging.getLogger(__name__)

DELAY_BETWEEN_STEPS = 2.0


@dataclass
class EnrichmentResult:
    """Detailed result of each pipeline stage."""
    item_id: str
    scraping: Optional[str] = None
    categorization: Optional[str] = None
    description: Optional[str] = None
    listing_updated: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors or all(
            s in ("ok", "skipped")
            for s in [self.scraping, self.categorization, self.description]
            if s is not None
        )

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "scraping": self.scraping,
            "categorization": self.categorization,
            "description": self.description,
            "listing_updated": self.listing_updated,
            "errors": self.errors,
            "success": self.success,
        }


@dataclass
class PipelineConfig:
    """Configuration for the enrichment pipeline."""
    delay_between_steps: float = DELAY_BETWEEN_STEPS
    max_scraping_attempts: int = 5
    use_ai_categorization: bool = True
    scrape_fn: Optional[Callable] = None
    get_existing_titles_fn: Optional[Callable] = None
    update_listing_fn: Optional[Callable] = None


class EnrichmentPipeline:
    """
    Stateful pipeline that runs the four enrichment stages.

    Accepts pluggable functions for data access (scraping, title lookup,
    listing update) so the core logic remains database-agnostic.
    """

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self._mapper: Optional[CategoryMapper] = None

    @property
    def mapper(self) -> CategoryMapper:
        if self._mapper is None:
            self._mapper = CategoryMapper()
        return self._mapper

    def enrich(self, item: Any, item_id: str = "") -> EnrichmentResult:
        """
        Run the full four-stage pipeline on a single item.

        Args:
            item: Object with attributes matching the enrichment schema.
            item_id: Identifier for logging and result tracking.

        Returns:
            EnrichmentResult with per-stage status and any errors.
        """
        result = EnrichmentResult(item_id=item_id or str(getattr(item, "id", "")))
        logger.info("Enrich START: %s", result.item_id)

        self._step_scraping(item, result)

        if result.scraping == "ok":
            time.sleep(self.config.delay_between_steps)

        self._step_categorization(item, result)
        self._step_description(item, result)
        self._step_update_listing(item, result)

        logger.info(
            "Enrich DONE: %s | scraping=%s cat=%s desc=%s listing=%s",
            result.item_id, result.scraping, result.categorization,
            result.description, result.listing_updated,
        )
        return result

    def _step_scraping(self, item: Any, result: EnrichmentResult):
        """
        Stage 1: External data fetching.

        Skips if:
        - No SKU/ASIN present
        - Max scraping attempts reached (marks for manual review)
        - All data fields already populated (description, images, features, price)

        On failure: increments attempt counter and flags for manual review
        when max attempts reached.
        """
        sku = (getattr(item, "sku", "") or "").strip()
        if not sku:
            result.scraping = "skipped"
            logger.info("  Scraping SKIP: %s no SKU", result.item_id)
            return

        attempts = getattr(item, "scraping_attempts", 0) or 0
        if attempts >= self.config.max_scraping_attempts:
            result.scraping = "max_attempts"
            logger.info(
                "  Scraping SKIP: %s has %d attempts (max=%d)",
                result.item_id, attempts, self.config.max_scraping_attempts,
            )
            return

        has_description = bool(getattr(item, "source_description", None))
        has_images = bool(getattr(item, "image_urls", None))
        has_features = bool(getattr(item, "source_features", None))
        has_price = getattr(item, "scraped_price", None) is not None

        if has_description and has_images and has_features and has_price:
            result.scraping = "skipped"
            logger.info("  Scraping SKIP: %s already has all data", result.item_id)
            return

        if not self.config.scrape_fn:
            result.scraping = "skipped"
            logger.info("  Scraping SKIP: no scrape_fn configured")
            return

        try:
            data = self.config.scrape_fn(sku)

            if data is None:
                item.scraping_attempts = attempts + 1
                if item.scraping_attempts >= self.config.max_scraping_attempts:
                    item.scraping_needs_manual = True
                    logger.warning(
                        "  Scraping MANUAL: %s SKU=%s reached max attempts (%d)",
                        result.item_id, sku, item.scraping_attempts,
                    )
                result.scraping = "failed"
                result.errors.append(f"Scraping failed for SKU {sku} (attempt {item.scraping_attempts})")
                return

            if data.get("title") and not getattr(item, "source_description", None):
                item.source_description = data["title"]
            if data.get("images") and not getattr(item, "image_urls", None):
                item.image_urls = data["images"]
            if data.get("features") and not getattr(item, "source_features", None):
                item.source_features = data["features"]
            if data.get("price") is not None and getattr(item, "scraped_price", None) is None:
                item.scraped_price = data["price"]
            elif data.get("price") is None:
                item.scraping_attempts = attempts + 1

            result.scraping = "ok"
            logger.info("  Scraping OK: %s SKU=%s", result.item_id, sku)

        except Exception as e:
            result.scraping = "failed"
            result.errors.append(f"Scraping error: {e}")
            logger.error("  Scraping ERROR: %s - %s", result.item_id, e)

    def _step_categorization(self, item: Any, result: EnrichmentResult):
        """
        Stage 2: Marketplace category classification.

        Uses three-tier hierarchy: direct mapping → AI → fallback.
        Skips if category already assigned.
        """
        current_category = (getattr(item, "marketplace_category", "") or "").strip()
        if current_category:
            result.categorization = "skipped"
            logger.info("  Categorization SKIP: %s already has '%s'", result.item_id, current_category)
            return

        dept = (getattr(item, "source_department", "") or "").strip()
        cat = (getattr(item, "source_category", "") or "").strip()
        desc = (getattr(item, "source_description", "") or "").strip()

        if not dept and not cat and not desc:
            result.categorization = "no_data"
            logger.info("  Categorization SKIP: %s no department/category/description", result.item_id)
            return

        try:
            category = self.mapper.classify(
                department=dept,
                category=cat,
                subcategory=(getattr(item, "source_subcategory", "") or "").strip(),
                description=desc,
                features=(getattr(item, "source_features", "") or "").strip(),
                use_ai=self.config.use_ai_categorization,
            )

            if category and category.strip():
                item.marketplace_category = category
                result.categorization = "ok"
                logger.info("  Categorization OK: %s -> '%s'", result.item_id, category)
            else:
                result.categorization = "failed"
                result.errors.append("Categorization returned empty")
                logger.warning("  Categorization FAIL: %s empty result", result.item_id)

        except Exception as e:
            result.categorization = "failed"
            result.errors.append(f"Categorization error: {e}")
            logger.error("  Categorization ERROR: %s - %s", result.item_id, e)

    def _step_description(self, item: Any, result: EnrichmentResult):
        """
        Stage 3: AI content generation.

        Generates title, description, keywords, hashtags, and extracts
        brand/model/color from the source data.

        Title deduplication: queries existing titles for the same SKU
        and passes them to the AI to force differentiation.

        Skips if all enrichment fields are already populated.
        """
        desc = (getattr(item, "source_description", "") or "").strip()
        if not desc:
            result.description = "no_data"
            logger.info("  Description SKIP: %s no source_description", result.item_id)
            return

        already_has = all([
            getattr(item, "wallapop_title", None),
            getattr(item, "wallapop_description", None),
            getattr(item, "keywords", None),
            getattr(item, "short_description", None),
            getattr(item, "related_keywords", None),
            getattr(item, "hashtags", None),
        ])
        if already_has:
            result.description = "skipped"
            logger.info("  Description SKIP: %s all fields populated", result.item_id)
            return

        try:
            features = (getattr(item, "source_features", "") or "").strip()
            sku = (getattr(item, "sku", "") or "").strip()

            existing_titles: list[str] = []
            if sku and self.config.get_existing_titles_fn:
                existing_titles = self.config.get_existing_titles_fn(sku, item)

            enrichment = generate_listing_content(
                desc, features, sku=sku,
                existing_titles=existing_titles or None,
            )

            if not enrichment:
                result.description = "failed"
                result.errors.append("AI returned no content")
                logger.warning("  Description FAIL: %s AI returned None", result.item_id)
                return

            updated = apply_enrichment(item, enrichment)
            if updated:
                result.description = "ok"
                logger.info(
                    "  Description OK: %s title='%s'",
                    result.item_id, enrichment.get("titulo_wallapop", ""),
                )
            else:
                result.description = "skipped"
                logger.info("  Description SKIP: %s no new fields", result.item_id)

        except Exception as e:
            result.description = "failed"
            result.errors.append(f"Description error: {e}")
            logger.error("  Description ERROR: %s - %s", result.item_id, e)

    def _step_update_listing(self, item: Any, result: EnrichmentResult):
        """
        Stage 4: Propagate enrichment to linked listings.

        Copies wallapop_title and wallapop_description to listing records.
        Only fills empty fields — the fully formatted description (with LPN,
        condition, keywords, etc.) is assembled at export time to reflect
        the most current data.
        """
        title = build_listing_title(item)
        description = build_listing_description(item)

        if not title and not description:
            logger.info("  Listing SKIP: %s no title/description to propagate", result.item_id)
            return

        if not self.config.update_listing_fn:
            logger.info("  Listing SKIP: no update_listing_fn configured")
            return

        try:
            self.config.update_listing_fn(item, title, description)
            result.listing_updated = True
            logger.info("  Listing UPDATE: %s", result.item_id)
        except Exception as e:
            result.errors.append(f"Listing update error: {e}")
            logger.error("  Listing UPDATE ERROR: %s - %s", result.item_id, e)


def enrich_item(item: Any, config: PipelineConfig | None = None, item_id: str = "") -> dict:
    """Convenience wrapper: run the full pipeline and return a dict result."""
    pipeline = EnrichmentPipeline(config)
    return pipeline.enrich(item, item_id=item_id).to_dict()
