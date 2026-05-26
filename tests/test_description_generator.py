"""Tests for the AI description generator."""
import pytest
from unittest.mock import patch

from src.enrichment.description_generator import (
    generate_listing_content,
    _truncate_title,
    MAX_TITLE_CHARS,
)


class TestTruncateTitle:
    """Word-boundary truncation for marketplace titles."""

    def test_short_title_unchanged(self):
        assert _truncate_title("Short title") == "Short title"

    def test_exact_max_unchanged(self):
        title = "A" * MAX_TITLE_CHARS
        assert _truncate_title(title) == title

    def test_long_title_truncated_at_word(self):
        title = "Aspiradora robot inteligente con sensor láser navegación"
        result = _truncate_title(title)
        assert len(result) <= MAX_TITLE_CHARS
        assert not result.endswith(" ")

    def test_single_long_word_truncated(self):
        title = "A" * 60
        result = _truncate_title(title)
        assert len(result) <= MAX_TITLE_CHARS

    def test_words_near_boundary(self):
        title = "X" * 48 + " YY"  # 51 chars
        result = _truncate_title(title)
        assert result == "X" * 48


class TestGenerateListingContent:
    """Tests for the full content generation flow."""

    MOCK_RESPONSE = {
        "palabras_clave": "auriculares,bluetooth,inalámbrico,música,sonido",
        "descripcion_5palabras": "Auriculares inalámbricos cancelación ruido",
        "titulo_wallapop": "Sony WH-1000XM5 auriculares bluetooth",
        "descripcion_mejorada": "Auriculares inalámbricos Sony con cancelación de ruido activa.",
        "palabras_clave_relacionadas": "audio,cascos,headphones,sony,noise,cancelling",
        "marca": "Sony",
        "modelo": "WH-1000XM5",
        "color": "Negro",
        "hashtags": "#sony,#auriculares,#bluetooth,#musica,#telovendo",
    }

    @patch("src.enrichment.description_generator.openai_client.chat_json")
    def test_basic_generation(self, mock_chat):
        mock_chat.return_value = self.MOCK_RESPONSE.copy()

        result = generate_listing_content("Sony WH-1000XM5 Wireless Headphones")

        assert result is not None
        assert result["marca"] == "Sony"
        assert result["modelo"] == "WH-1000XM5"
        assert "titulo_wallapop" in result
        assert len(result["titulo_wallapop"]) <= MAX_TITLE_CHARS

    @patch("src.enrichment.description_generator.openai_client.chat_json")
    def test_title_auto_truncated(self, mock_chat):
        response = self.MOCK_RESPONSE.copy()
        response["titulo_wallapop"] = "A" * 60  # Over limit
        mock_chat.return_value = response

        result = generate_listing_content("Some product description")

        assert result is not None
        assert len(result["titulo_wallapop"]) <= MAX_TITLE_CHARS

    @patch("src.enrichment.description_generator.openai_client.chat_json")
    def test_existing_titles_passed(self, mock_chat):
        mock_chat.return_value = self.MOCK_RESPONSE.copy()
        existing = ["Sony auriculares BT cancelación", "Cascos Sony WH-1000XM5"]

        result = generate_listing_content(
            "Sony WH-1000XM5",
            sku="B0BX2K9GQ6",
            existing_titles=existing,
        )

        assert result is not None
        prompt_used = mock_chat.call_args[0][0]
        assert "YA USADOS" in prompt_used
        assert existing[0] in prompt_used

    @patch("src.enrichment.description_generator.openai_client.chat_json")
    def test_features_included_in_prompt(self, mock_chat):
        mock_chat.return_value = self.MOCK_RESPONSE.copy()

        generate_listing_content(
            "Sony Headphones",
            features="30h battery life\nBluetooth 5.2",
        )

        prompt_used = mock_chat.call_args[0][0]
        assert "30h battery life" in prompt_used
        assert "Bluetooth 5.2" in prompt_used

    @patch("src.enrichment.description_generator.openai_client.chat_json")
    def test_sku_included_in_prompt(self, mock_chat):
        mock_chat.return_value = self.MOCK_RESPONSE.copy()

        generate_listing_content("Product", sku="B0BX2K9GQ6")

        prompt_used = mock_chat.call_args[0][0]
        assert "B0BX2K9GQ6" in prompt_used

    @patch("src.enrichment.description_generator.openai_client.chat_json")
    def test_api_failure_returns_none(self, mock_chat):
        mock_chat.return_value = None

        result = generate_listing_content("Product description")
        assert result is None

    @patch("src.enrichment.description_generator.openai_client.chat_json")
    def test_policy_terms_banned_in_prompt(self, mock_chat):
        mock_chat.return_value = self.MOCK_RESPONSE.copy()

        generate_listing_content("Some TV product")

        prompt_used = mock_chat.call_args[0][0]
        assert "satélite" in prompt_used.lower() or "NUNCA uses" in prompt_used
