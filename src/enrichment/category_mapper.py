"""
Three-tier product categorization for marketplace listings.

Classification hierarchy:
1. Direct mapping — JSON lookup from Amazon department/category to Wallapop category.
   Covers ~80% of items with zero API cost.
2. AI classification — OpenAI call with the full category taxonomy as context.
   Used when no mapping exists. Costs ~$0.001 per item.
3. Department fallback — Hardcoded map from Amazon department to a safe default.
   Guarantees every item gets a category.

The category taxonomy is loaded from a JSON tree and flattened into valid
leaf paths (e.g., "Hogar y jardín > Cocina > Pequeño electrodoméstico").
"""
import json
import logging
from pathlib import Path
from typing import Optional

from . import openai_client

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

INVALID_RESPONSES = [
    "no hay descripción",
    "no hay descripcion",
    "por favor, proporciona",
    "no se puede clasificar",
    "no proporcionada",
]

DEPARTMENT_FALLBACK = {
    "Home": "Hogar y jardín",
    "Pet Products": "Hogar y jardín > Artículos para mascotas",
    "Wireless": "Tecnología y electrónica",
    "Camera": "Tecnología y electrónica",
    "Home Entertainment": "Tecnología y electrónica",
    "Electronics": "Tecnología y electrónica",
    "Office Product": "Tecnología y electrónica",
    "Automotive": "Industria y agricultura",
    "Sports": "Deporte y ocio",
    "Fashion": "Moda y accesorios",
    "Health & Beauty": "Moda y accesorios > Belleza",
    "Toys": "Niños y bebés > Juguetes, juegos y peluches",
    "": "Hogar y jardín",
}


class CategoryMapper:
    """
    Maps Amazon department/category pairs to Wallapop categories
    using a three-tier classification strategy.
    """

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
        self.valid_paths = self._flatten_taxonomy(taxonomy)

    @staticmethod
    def _load_json(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _flatten_taxonomy(self, node: dict, prefix: list | None = None) -> list[str]:
        """Recursively flatten the category tree into '>' separated leaf paths."""
        prefix = prefix or []
        paths: list[str] = []
        for cat, sub in node.items():
            current = prefix + [cat]
            if sub:
                paths += self._flatten_taxonomy(sub, current)
            else:
                paths.append(" > ".join(current))
        return paths

    def get_mapped_category(self, department: str, category: str) -> Optional[str]:
        """
        Tier 1: Direct JSON lookup.

        Checks department+category first, then department default (empty string key).
        Returns None if no mapping exists.
        """
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
        """
        Tier 2: AI classification using OpenAI.

        Sends the full product context along with the available category
        taxonomy. Temperature is set to 0.1 for deterministic output.
        Returns a "Category > Subcategory" path string.
        """
        product_context = "; ".join([
            description.strip(),
            features.strip(),
            f"Department: {department}",
            f"Category: {category}",
            f"Subcategory: {subcategory}",
        ])

        prompt = f"""
**Contexto**: Eres un clasificador de productos para marketplace. 
**Instrucciones**:
1. Identifica la CATEGORÍA PRINCIPAL que mejor describa el producto.
2. Luego selecciona la SUBCATEGORÍA MÁS APROPIADA.
3. Usa EXCLUSIVAMENTE categorías de esta lista:

**Categorías principales disponibles**:
{chr(10).join(f"- {cat}" for cat in self.top_level_categories)}

**Reglas**:
- Es MÁS IMPORTANTE que la categoría principal sea correcta que la subcategoría exacta.
- Si no estás seguro de la subcategoría, elige una general pero mantén la categoría principal correcta.
- NO inventes categorías nuevas.
- Formato: "Categoría > Subcategoría" (2 niveles son suficientes)

**Descripción del producto**: {product_context}

**Respuesta** (solo la ruta de categoría, sin explicaciones):
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
        Classify a product through the three-tier hierarchy.

        Always returns a non-empty string:
        1. Direct mapping (free, instant)
        2. AI classification (costs ~$0.001, ~1s latency)
        3. Department fallback (free, instant, less precise)
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

        fallback = DEPARTMENT_FALLBACK.get(department, DEPARTMENT_FALLBACK[""])
        logger.warning("Fallback for '%s': %s", department, fallback)
        return fallback

    @staticmethod
    def _is_invalid(value: str) -> bool:
        """Check if AI response is a refusal or error message."""
        if not value:
            return True
        v = value.strip().lower()
        return any(phrase in v for phrase in INVALID_RESPONSES)
