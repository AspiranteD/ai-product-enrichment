"""
AI-powered product listing content generator.

Generates marketplace-optimized content from source product data:
- Title (max 50 chars, word-boundary truncation)
- Description (max 250 chars, features + target audience)
- Keywords, related keywords, hashtags
- Brand, model, color extraction

Key design decisions:
- Title uniqueness: accepts existing titles from the same SKU to force
  the AI to differentiate (e.g., include model number, capacity, color).
- Policy compliance: title instructions explicitly ban terms that
  trigger marketplace policy violations (satellite, decoder, IPTV, etc.).
- JSON response format: uses OpenAI's response_format=json_object for
  guaranteed parseable output.
- Locale-aware: prompts in Spanish for the target marketplace.
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
    sku: str = "",
    existing_titles: list[str] | None = None,
) -> Optional[dict]:
    """
    Generate enrichment fields for a product listing.

    Args:
        description: Source product description.
        features: Additional product features/bullet points.
        sku: Product SKU/ASIN. Used for title uniqueness context.
        existing_titles: Titles already assigned to other items with the same SKU.
            The AI is instructed to avoid duplicating these, forcing it to
            differentiate by model number, capacity, voltage, color, etc.

    Returns:
        dict with keys: palabras_clave, descripcion_5palabras, titulo_wallapop,
        descripcion_mejorada, palabras_clave_relacionadas, marca, modelo,
        color, hashtags. Or None on failure.
    """
    text = description.strip()
    if features and features.strip():
        text += "\nCaracterísticas:\n" + features.strip()

    uniqueness_block = ""
    if existing_titles:
        sample = existing_titles[:10]
        title_list = "\n".join(f'           - "{t}"' for t in sample)
        uniqueness_block = f"""
        🔹 **Títulos YA USADOS por otros productos de la misma tienda (NO repitas ninguno):**
{title_list}

        El título que generes debe ser diferente a todos los anteriores aunque sea el mismo tipo de producto.
        Para diferenciarlo: incluye el modelo exacto, número de referencia, capacidad, voltaje, tamaño,
        compatibilidad específica u otra característica única del producto.
"""

    sku_block = f"\n        🔹 **SKU del producto:** {sku}" if sku else ""

    prompt = f"""
        Eres un experto en marketing digital para marketplaces españoles.

        A partir de la siguiente información del producto, genera una ficha optimizada para marketplaces como Wallapop.  
        **Sigue las instrucciones al pie de la letra y responde SOLO con un JSON válido, sin texto extra.**

        ---
        {sku_block}
        🔹 **Información del producto:**  
        {text}
        {uniqueness_block}
        ---

        🔹 **Instrucciones de generación:**  
        1. **palabras_clave**: 5 palabras clave principales, separadas por coma, en castellano (excepto marcas o nombres comerciales).
        2. **descripcion_5palabras**: Describe el articulo en 5 palabras, usando términos de la descripción original.
        3. **titulo_wallapop**: Título atractivo para Wallapop, máximo 50 caracteres, usando palabras clave y la descripción de 5 palabras.  
           - Nunca menciones el estado del artículo (no pongas "nuevo", "perfecto estado", etc.).
           - Incluye siempre la marca si es conocida. Incluye el modelo o referencia si ayuda a diferenciar el producto.
           - Usa palabras en castellano, salvo marcas o nombres comerciales (ejemplo: "Smartphone" sí, "thermostat" no, usa "termostato").
           - NUNCA uses en título ni descripción: satélite, decodificador, emulador, IPTV, Kodi, jailbreak, TV box, Android TV (usa TDT, sintonizador, televisor, etc.).
           - El título debe describir ESTE producto concreto, no ser genérico para toda la gama.
        4. **descripcion_mejorada**: Descripción de máximo 250 caracteres, incluyendo uso y público objetivo, usando palabras clave generadas.  
           - No inventes accesorios ni unidades extra.
           - No menciones el estado del artículo.
        5. **palabras_clave_relacionadas**: 10-12 palabras clave relacionadas, separadas por coma, en castellano.
        6. **marca**: Marca del producto (vacío si no está claro).
        7. **modelo**: Modelo del producto (vacío si no está claro).
        8. **color**: Color del producto (vacío si no está claro o hay varios posibles).
        9. **hashtags**: 6 hashtags relevantes, separados por coma, en minúsculas y en castellano (excepto marcas).  
           - El último hashtag debe ser siempre "#telovendo".
           - Formato: #palabra1,#palabra2,#palabra3,#palabra4,#palabra5,#telovendo

        ---

        🔹 **Ejemplo de formato de respuesta:**
        {{
            "palabras_clave": "monopoly,juego de mesa,dinero,juguete,juego en familia",
            "descripcion_5palabras": "Juego mesa familiar con dinero",
            "titulo_wallapop": "Monopoly juego de mesa familiar dinero",
            "descripcion_mejorada": "Divertido juego de mesa Monopoly para toda la familia. Ideal para reuniones y tardes de ocio. Incluye tablero, fichas y dinero ficticio. Para niños y adultos.",
            "palabras_clave_relacionadas": "tablero,cartas,estrategia,diversión,niños,adultos,regalo,amigos,ocio,entretenimiento,familia,competencia",
            "marca": "Hasbro",
            "modelo": "Monopoly Classic",
            "color": "",
            "hashtags": "#monopoly,#juegodemesa,#dinero,#juguete,#telovendo"
        }}

        ---

        🔹 **IMPORTANTE:**
        - Devuelve SOLO el JSON válido, sin texto antes o después.
        - No inventes datos que no estén en la información original.
        - Usa siempre castellano salvo marcas/modelos.
        - Si no puedes rellenar marca, modelo o color, deja el campo vacío ("").

        ---
        """

    result = openai_client.chat_json(prompt, temperature=0.2)
    if not result:
        return None

    title = result.get("titulo_wallapop", "")
    if len(title) > MAX_TITLE_CHARS:
        logger.info("Title truncated from %d to %d chars", len(title), MAX_TITLE_CHARS)
        result["titulo_wallapop"] = _truncate_title(title)

    return result
