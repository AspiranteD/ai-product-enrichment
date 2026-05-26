"""
Listing content assembly from enrichment data.

Maps AI-generated fields to item database fields and handles the
idempotent write pattern: only populate empty fields, never overwrite
existing content.

Field mapping:
    AI output key              →  Database field
    ────────────────────────────────────────────
    palabras_clave             →  keywords
    descripcion_5palabras      →  short_description
    titulo_wallapop            →  wallapop_title
    descripcion_mejorada       →  wallapop_description
    palabras_clave_relacionadas→  related_keywords
    marca                      →  brand
    modelo                     →  model
    color                      →  color
    hashtags                   →  hashtags
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

FIELD_MAP = {
    "palabras_clave": "keywords",
    "descripcion_5palabras": "short_description",
    "titulo_wallapop": "wallapop_title",
    "descripcion_mejorada": "wallapop_description",
    "palabras_clave_relacionadas": "related_keywords",
    "marca": "brand",
    "modelo": "model",
    "color": "color",
    "hashtags": "hashtags",
}

ENRICHMENT_FIELDS = [
    "wallapop_title",
    "wallapop_description",
    "keywords",
    "short_description",
    "related_keywords",
    "hashtags",
]


def apply_enrichment(item: Any, enrichment: dict) -> bool:
    """
    Apply AI-generated fields to an item object.

    Only writes to fields that are currently empty (None or "").
    This ensures manual edits are never overwritten.

    Args:
        item: Object with settable attributes matching FIELD_MAP values.
        enrichment: Dict from generate_listing_content().

    Returns:
        True if at least one field was populated.
    """
    updated = False
    for src_key, db_field in FIELD_MAP.items():
        value = enrichment.get(src_key, "")
        if value and not getattr(item, db_field, None):
            setattr(item, db_field, value)
            updated = True
    return updated


def get_missing_fields(item: Any) -> list[str]:
    """Return list of enrichment field names that are still empty on the item."""
    return [f for f in ENRICHMENT_FIELDS if not getattr(item, f, None)]


def is_fully_enriched(item: Any) -> bool:
    """Check if all enrichment fields are populated."""
    return all(getattr(item, f, None) for f in ENRICHMENT_FIELDS)


def build_listing_title(item: Any) -> str:
    """Extract the wallapop_title field, stripped and ready for export."""
    return (getattr(item, "wallapop_title", "") or "").strip()


def build_listing_description(item: Any) -> str:
    """Extract the wallapop_description field, stripped and ready for export."""
    return (getattr(item, "wallapop_description", "") or "").strip()
