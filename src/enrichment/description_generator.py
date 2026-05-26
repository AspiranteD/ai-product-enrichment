"""
AI-powered product description generator.

Takes raw product data (title, features, identifiers) and generates
marketplace-optimized content: title, description, keywords, hashtags,
brand/model/color extraction.

Uses structured JSON output from OpenAI for reliable parsing.
"""
import logging
from typing import Optional

from . import openai_client

logger = logging.getLogger(__name__)

MAX_TITLE_CHARS = 50


def _truncate_title(title: str, max_len: int = MAX_TITLE_CHARS) -> str:
    """Truncate to the last complete word within max_len characters."""
    if len(title) <= max_len:
        return title
    cut = title[:max_len].rstrip()
    if len(title) > max_len and not title[max_len].isspace():
        cut = cut.rsplit(" ", 1)[0]
    return cut


def generate_listing_content(
    description: str,
    features: str = "",
    product_id: str = "",
    existing_titles: list[str] | None = None,
) -> Optional[dict]:
    """
    Generate enriched listing content from raw product data.

    Args:
        description: Source product description (e.g. from Amazon).
        features: Additional product features/bullet points.
        product_id: Product identifier (ASIN, SKU, etc.) for title uniqueness.
        existing_titles: Titles already used by similar products in the same
            store, so the AI avoids generating duplicates.

    Returns:
        Dict with keys: keywords, short_description, listing_title,
        enhanced_description, related_keywords, brand, model, color, hashtags.
        Returns None on failure.
    """
    text = description.strip()
    if features and features.strip():
        text += "\nFeatures:\n" + features.strip()

    uniqueness_block = ""
    if existing_titles:
        sample = existing_titles[:10]
        items = "\n".join(f'           - "{t}"' for t in sample)
        uniqueness_block = f"""
        **Titles ALREADY USED by other products in the same store (DO NOT repeat any):**
{items}

        The title you generate must be different from all of the above, even if it's the same type of product.
        To differentiate: include the exact model, reference number, capacity, voltage, size,
        specific compatibility, or another unique characteristic.
"""

    id_block = f"\n        **Product ID:** {product_id}" if product_id else ""

    prompt = f"""
        You are a digital marketing expert for online marketplaces.

        Given the following product information, generate an optimized listing.
        **Follow instructions exactly and respond ONLY with valid JSON, no extra text.**

        ---
        {id_block}
        **Product information:**
        {text}
        {uniqueness_block}
        ---

        **Generation instructions:**
        1. **keywords**: 5 main keywords, comma-separated.
        2. **short_description**: Describe the item in 5 words.
        3. **listing_title**: Attractive title, max 50 characters, using keywords.
           - Never mention condition (don't say "new", "perfect condition", etc.).
           - Always include the brand if known. Include model/reference if it helps differentiate.
        4. **enhanced_description**: Description of max 250 characters, including use case and target audience.
           - Don't invent accessories or extra units.
           - Don't mention the item's condition.
        5. **related_keywords**: 10-12 related keywords, comma-separated.
        6. **brand**: Product brand (empty if unclear).
        7. **model**: Product model (empty if unclear).
        8. **color**: Product color (empty if unclear or multiple possible).
        9. **hashtags**: 6 relevant hashtags, comma-separated, lowercase.

        ---

        **Example response format:**
        {{
            "keywords": "monopoly,board game,family,toy,strategy",
            "short_description": "Classic family board game set",
            "listing_title": "Monopoly Classic Board Game Family",
            "enhanced_description": "Fun Monopoly board game for the whole family. Perfect for gatherings and leisure. Includes board, tokens and play money. For kids and adults.",
            "related_keywords": "board,cards,strategy,fun,kids,adults,gift,friends,leisure,entertainment,family,competition",
            "brand": "Hasbro",
            "model": "Monopoly Classic",
            "color": "",
            "hashtags": "#monopoly,#boardgame,#family,#toy,#strategy,#hasbro"
        }}

        ---

        **IMPORTANT:**
        - Return ONLY valid JSON, no text before or after.
        - Do not invent data not present in the original information.
        - If brand, model, or color cannot be determined, leave the field empty ("").

        ---
        """

    result = openai_client.chat_json(prompt, temperature=0.2)
    if not result:
        return None

    title = result.get("listing_title", "")
    if len(title) > MAX_TITLE_CHARS:
        logger.info("Title truncated from %d to %d chars", len(title), MAX_TITLE_CHARS)
        result["listing_title"] = _truncate_title(title)

    return result
