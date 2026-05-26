"""
AI-powered product category mapper.

Classification hierarchy:
  1. Direct mapping via JSON lookup tables
  2. AI classification via OpenAI
  3. Fallback by source department

Supports any marketplace category taxonomy via configurable JSON files.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from . import openai_client

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"

INVALID_RESPONSES = [
    "no description",
    "no hay descripción",
    "please provide",
    "cannot classify",
    "not provided",
]

FALLBACK_MAP = {
    "Home": "Home & Garden",
    "Pet Products": "Home & Garden > Pet Supplies",
    "Wireless": "Technology & Electronics",
    "Camera": "Technology & Electronics",
    "Home Entertainment": "Technology & Electronics",
    "Electronics": "Technology & Electronics",
    "Office Product": "Technology & Electronics",
    "Automotive": "Industry & Agriculture",
    "Sports": "Sports & Leisure",
    "Fashion": "Fashion & Accessories",
    "Health & Beauty": "Fashion & Accessories > Beauty",
    "Toys": "Kids & Baby > Toys & Games",
    "": "Home & Garden",
}


class CategoryMapper:
    """Maps source product categories to marketplace-specific categories."""

    def __init__(
        self,
        mapping_path: str | Path | None = None,
        taxonomy_path: str | Path | None = None,
    ):
        mapping_path = Path(mapping_path) if mapping_path else _DATA_DIR / "category_mapping.json"
        taxonomy_path = Path(taxonomy_path) if taxonomy_path else _DATA_DIR / "category_taxonomy.json"

        self.mapping = self._load_json(mapping_path)
        taxonomy = self._load_json(taxonomy_path)
        self.top_level_categories = list(taxonomy.keys())
        self.valid_paths = self._flatten_paths(taxonomy)

    @staticmethod
    def _load_json(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _flatten_paths(self, node: dict, path: list | None = None) -> list[str]:
        """Recursively flatten the taxonomy tree into 'Cat > Subcat > ...' paths."""
        path = path or []
        paths: list[str] = []
        for cat, sub in node.items():
            current = path + [cat]
            if sub:
                paths += self._flatten_paths(sub, current)
            else:
                paths.append(" > ".join(current))
        return paths

    def get_mapped_category(self, department: str, category: str) -> Optional[str]:
        """Attempt direct lookup in the mapping table."""
        if not department or department not in self.mapping:
            return None
        dept_map = self.mapping[department]
        if category in dept_map:
            return dept_map[category]
        if "" in dept_map:
            return dept_map[""]
        return None

    def classify_with_ai(
        self,
        department: str,
        category: str,
        subcategory: str = "",
        description: str = "",
        features: str = "",
    ) -> Optional[str]:
        """Use OpenAI to classify the product into the taxonomy."""
        full_description = "; ".join([
            description.strip(),
            features.strip(),
            f"Department: {department}",
            f"Category: {category}",
            f"Subcategory: {subcategory}",
        ])

        prompt = f"""
**Context**: You are a product classifier for an online marketplace.
**Instructions**:
1. Identify the TOP-LEVEL CATEGORY that best describes the product.
2. Then select the MOST APPROPRIATE SUBCATEGORY.
3. Use EXCLUSIVELY categories from this list:

**Available top-level categories**:
{chr(10).join(f"- {cat}" for cat in self.top_level_categories)}

**Rules**:
- Getting the top-level category right is MORE IMPORTANT than the exact subcategory.
- If unsure about the subcategory, pick a general one but keep the top-level correct.
- DO NOT invent new categories.
- Format: "Category > Subcategory" (2 levels are sufficient)

**Product description**: {full_description}

**Response** (category path only, no explanations):
"""
        return openai_client.chat_text(prompt, temperature=0.1, max_tokens=100)

    def classify(
        self,
        department: str,
        category: str,
        subcategory: str = "",
        description: str = "",
        features: str = "",
        use_ai: bool = True,
    ) -> str:
        """
        Classify a product. Hierarchy: direct mapping -> AI -> fallback.
        Always returns a non-empty string.
        """
        department = (department or "").strip()
        category = (category or "").strip()

        mapped = self.get_mapped_category(department, category)
        if mapped:
            logger.info("Direct mapping: %s/%s -> %s", department, category, mapped)
            return mapped

        if use_ai:
            logger.info("No mapping for %s/%s, calling AI...", department, category)
            ai_result = self.classify_with_ai(
                department, category,
                subcategory=(subcategory or "").strip(),
                description=description,
                features=features,
            )
            if ai_result and not self._is_invalid(ai_result):
                logger.info("AI classified: %s", ai_result)
                return ai_result
            logger.warning("AI returned invalid response: %s", ai_result)

        fallback = FALLBACK_MAP.get(department, FALLBACK_MAP[""])
        logger.warning("Fallback for '%s': %s", department, fallback)
        return fallback

    @staticmethod
    def _is_invalid(value: str) -> bool:
        if not value:
            return True
        v = value.strip().lower()
        return any(phrase in v for phrase in INVALID_RESPONSES)
