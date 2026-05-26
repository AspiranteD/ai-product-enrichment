"""
Listing title and description assembler.

Constructs formatted marketplace listings from enriched product data,
applying condition-based prefixes, structured sections (brand/model,
description, keywords), and policy compliance sanitization.
"""
from typing import Optional

from .policy_sanitizer import sanitize_text


def build_listing_title(
    enriched_title: str = "",
    source_description: str = "",
    condition_code: str = "PERFECT",
    existing_title: str = "",
) -> str:
    """
    Build a listing title with condition-based emoji prefix.

    Priority: enriched_title > existing_title > source_description.

    PERFECT    -> clean title (max 50 chars)
    DAMAGED    -> warning prefix + title (max 46 chars base)
    FOR_PARTS  -> broken prefix + title (max 46 chars base)
    """
    base = _clean(enriched_title)
    if not base:
        base = _clean(existing_title)
    if not base:
        base = _clean(source_description)
    if not base:
        return ""

    ccode = _clean(condition_code) or "PERFECT"
    if ccode == "FOR_PARTS":
        return sanitize_text(f"💔 - {base[:46]}")
    elif ccode == "DAMAGED":
        return sanitize_text(f"💰 - {base[:46]}")
    return sanitize_text(base[:50], for_title=True)


_FORMATTED_HEADERS = ("✅", "🛑", "⚠️", "🏷️")


def _is_already_formatted(text: str) -> bool:
    if not text:
        return False
    return text.lstrip().startswith(_FORMATTED_HEADERS)


def build_listing_description(
    item_id: str = "",
    condition_code: str = "PERFECT",
    condition_notes: str = "",
    brand: str = "",
    model: str = "",
    color: str = "",
    enriched_description: str = "",
    source_description: str = "",
    source_features: str = "",
    location: str = "",
    keywords: str = "",
    related_keywords: str = "",
    short_description: str = "",
    existing_description: str = "",
) -> str:
    """
    Assemble a full formatted listing description with structured sections:

        ✅ EXCELLENT CONDITION ✅

        🏷️ Brand: X
        🔖 Model: Y

        📝 Description:
        ... ITEM-ID - LOCATION

        🔑 Keywords: ...
        🔗 Related: ...

        📦 short description

    If existing_description is already formatted, reuses it to avoid
    duplicating headers.
    """
    item_id = _clean(item_id)
    condition_code = _clean(condition_code) or "PERFECT"

    ed = _clean(existing_description)
    if ed and _is_already_formatted(ed) and not _clean(enriched_description):
        if condition_code == "PERFECT":
            return ed

    blocks: list[str] = []

    # 1. Condition block
    condition_txt = _condition_block(condition_code, _clean(condition_notes))
    if condition_txt:
        blocks.append(condition_txt)

    # 2. Product info
    info = _product_info_block(brand, model, color)
    if info:
        blocks.append(info)

    # 3. Description + ID + Location
    desc = _clean(enriched_description)
    if not desc:
        desc = _clean(source_description)
        if desc:
            desc = desc[:300]

    if desc:
        suffix_parts = []
        if item_id:
            suffix_parts.append(item_id)
        loc = _clean(location)
        if loc:
            suffix_parts.append(loc)
        suffix = " - ".join(suffix_parts)

        desc_block = f"📝 Description:\n{desc}"
        if suffix:
            desc_block += f" {suffix}"
        blocks.append(desc_block)
    elif item_id:
        blocks.append(f"📝 {item_id}")

    # 4. Keywords
    kw = _clean(keywords)
    rel = _clean(related_keywords)
    if kw:
        kw_block = f"🔑 Keywords: {kw}"
        if rel:
            kw_block += f"\n🔗 Related: {rel}"
        blocks.append(kw_block)

    # 5. Short description
    short = _clean(short_description)
    if short:
        blocks.append(f"📦 {short}")

    # Minimal fallback
    if not blocks:
        min_parts = []
        if item_id:
            min_parts.append(f"📦 ID: {item_id}")
        loc = _clean(location)
        if loc:
            min_parts.append(f"📍 Location: {loc}")
        feat = _clean(source_features)
        amz = _clean(source_description)
        if feat:
            min_parts.append(f"📋 {feat[:200]}")
        elif amz:
            min_parts.append(f"📋 {amz[:200]}")
        blocks = min_parts

    return sanitize_text("\n\n".join(blocks))


def _clean(value: Optional[str]) -> str:
    if not value:
        return ""
    s = str(value).strip()
    if s.lower() in ("nan", "none", ""):
        return ""
    return s


def _condition_block(condition_code: str, notes: str) -> str:
    conditions = {
        "PERFECT": ("✅", "EXCELLENT CONDITION", "✅"),
        "FOR_PARTS": ("🛑⚠️", "FOR REPAIR OR PARTS", "⚠️🛑"),
        "DAMAGED": ("⚠️", "READ CAREFULLY", "⚠️"),
    }
    entry = conditions.get(condition_code)
    if not entry:
        return ""
    prefix, label, suffix = entry
    if notes and condition_code == "DAMAGED":
        return f"{prefix} {label}: {notes} {suffix}"
    elif notes:
        return f"{prefix} {label} {suffix} - {notes}"
    return f"{prefix} {label} {suffix}"


def _product_info_block(brand: str, model: str, color: str) -> str:
    parts = []
    b, m, c = _clean(brand), _clean(model), _clean(color)
    if b:
        parts.append(f"🏷️ Brand: {b}")
    if m:
        parts.append(f"🔖 Model: {m}")
    if c:
        parts.append(f"🎨 Color: {c}")
    return "\n".join(parts)
