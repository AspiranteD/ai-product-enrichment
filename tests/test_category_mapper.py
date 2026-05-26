"""Tests for the three-tier category mapper."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.enrichment.category_mapper import CategoryMapper, DEPARTMENT_FALLBACK, INVALID_RESPONSES


@pytest.fixture
def tmp_data(tmp_path):
    """Create temporary mapping and taxonomy files for testing."""
    mapping = {
        "Electronics": {
            "Headphones": "Tecnología y electrónica > Audio",
            "Cameras": "Tecnología y electrónica > Fotografía",
            "": "Tecnología y electrónica",
        },
        "Home": {
            "Kitchen": "Hogar y jardín > Cocina",
            "Bathroom": "Hogar y jardín > Baño y accesorios",
        },
        "Sports": {
            "Fitness": "Deporte y ocio > Fitness, running y yoga",
        },
    }
    taxonomy = {
        "Tecnología y electrónica": {
            "Audio": {},
            "Fotografía": {},
            "Telefonía": {
                "Móviles": {},
                "Accesorios": {},
            },
        },
        "Hogar y jardín": {
            "Cocina": {},
            "Baño y accesorios": {},
        },
        "Deporte y ocio": {
            "Fitness, running y yoga": {},
        },
    }

    mapping_path = tmp_path / "category_mapping.json"
    taxonomy_path = tmp_path / "category_taxonomy.json"

    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    taxonomy_path.write_text(json.dumps(taxonomy), encoding="utf-8")

    return mapping_path, taxonomy_path


@pytest.fixture
def mapper(tmp_data):
    mapping_path, taxonomy_path = tmp_data
    return CategoryMapper(mapping_path=mapping_path, taxonomy_path=taxonomy_path)


class TestDirectMapping:
    """Tier 1: JSON lookup tests."""

    def test_exact_match(self, mapper):
        result = mapper.get_mapped_category("Electronics", "Headphones")
        assert result == "Tecnología y electrónica > Audio"

    def test_department_default(self, mapper):
        result = mapper.get_mapped_category("Electronics", "UnknownCategory")
        assert result == "Tecnología y electrónica"

    def test_unknown_department(self, mapper):
        result = mapper.get_mapped_category("Fashion", "Shoes")
        assert result is None

    def test_empty_department(self, mapper):
        result = mapper.get_mapped_category("", "Anything")
        assert result is None


class TestTaxonomyFlattening:
    """Verifies the taxonomy tree is flattened correctly."""

    def test_leaf_paths_generated(self, mapper):
        assert "Tecnología y electrónica > Audio" in mapper.valid_paths
        assert "Tecnología y electrónica > Telefonía > Móviles" in mapper.valid_paths
        assert "Hogar y jardín > Cocina" in mapper.valid_paths

    def test_top_level_categories(self, mapper):
        assert "Tecnología y electrónica" in mapper.top_level_categories
        assert "Hogar y jardín" in mapper.top_level_categories
        assert "Deporte y ocio" in mapper.top_level_categories


class TestClassifyHierarchy:
    """Tests the full three-tier classification flow."""

    def test_direct_mapping_preferred(self, mapper):
        result = mapper.classify("Electronics", "Headphones")
        assert result == "Tecnología y electrónica > Audio"

    def test_ai_called_when_no_mapping(self, mapper):
        with patch.object(mapper, "classify_with_ai", return_value="Moda y accesorios > Zapatos"):
            result = mapper.classify("Fashion", "Shoes", use_ai=True)
            assert result == "Moda y accesorios > Zapatos"

    def test_fallback_when_ai_fails(self, mapper):
        with patch.object(mapper, "classify_with_ai", return_value=None):
            result = mapper.classify("Sports", "Swimming", use_ai=True)
            assert result == DEPARTMENT_FALLBACK["Sports"]

    def test_fallback_when_ai_invalid(self, mapper):
        with patch.object(mapper, "classify_with_ai", return_value="no se puede clasificar"):
            result = mapper.classify("Electronics", "Quantum", use_ai=True)
            assert result == DEPARTMENT_FALLBACK.get("Electronics", DEPARTMENT_FALLBACK[""])

    def test_fallback_when_ai_disabled(self, mapper):
        result = mapper.classify("Fashion", "Shoes", use_ai=False)
        assert result == DEPARTMENT_FALLBACK.get("Fashion", DEPARTMENT_FALLBACK[""])

    def test_unknown_department_fallback(self, mapper):
        with patch.object(mapper, "classify_with_ai", return_value=None):
            result = mapper.classify("AlienTech", "Warp", use_ai=True)
            assert result == DEPARTMENT_FALLBACK[""]

    def test_empty_inputs_fallback(self, mapper):
        with patch.object(mapper, "classify_with_ai", return_value=None):
            result = mapper.classify("", "")
            assert result == DEPARTMENT_FALLBACK[""]


class TestInvalidResponseDetection:
    """Tests that AI refusal messages are correctly identified."""

    @pytest.mark.parametrize("response", INVALID_RESPONSES)
    def test_invalid_responses_detected(self, response):
        assert CategoryMapper._is_invalid(response) is True

    def test_valid_response_accepted(self):
        assert CategoryMapper._is_invalid("Tecnología y electrónica > Audio") is False

    def test_none_is_invalid(self):
        assert CategoryMapper._is_invalid(None) is True

    def test_empty_is_invalid(self):
        assert CategoryMapper._is_invalid("") is True
