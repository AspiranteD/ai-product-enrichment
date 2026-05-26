"""Tests for the AI-powered category mapper."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.enrichment.category_mapper import CategoryMapper, FALLBACK_MAP


def _create_test_files():
    """Create temporary JSON files for testing."""
    mapping = {
        "Electronics": {
            "Headphones": "Technology > Audio",
            "Cameras": "Technology > Photography",
            "": "Technology > General",
        },
        "Home": {
            "Kitchen": "Home & Garden > Kitchen",
        },
    }
    taxonomy = {
        "Technology": {
            "Audio": {},
            "Photography": {},
            "General": {},
        },
        "Home & Garden": {
            "Kitchen": {},
            "Garden": {},
        },
        "Sports & Leisure": {
            "Fitness": {},
        },
    }
    mapping_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    taxonomy_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(mapping, mapping_file)
    json.dump(taxonomy, taxonomy_file)
    mapping_file.close()
    taxonomy_file.close()
    return mapping_file.name, taxonomy_file.name


class TestDirectMapping:

    def test_exact_match(self):
        m, t = _create_test_files()
        mapper = CategoryMapper(mapping_path=m, taxonomy_path=t)
        result = mapper.get_mapped_category("Electronics", "Headphones")
        assert result == "Technology > Audio"

    def test_default_mapping(self):
        m, t = _create_test_files()
        mapper = CategoryMapper(mapping_path=m, taxonomy_path=t)
        result = mapper.get_mapped_category("Electronics", "UnknownCategory")
        assert result == "Technology > General"

    def test_unknown_department(self):
        m, t = _create_test_files()
        mapper = CategoryMapper(mapping_path=m, taxonomy_path=t)
        result = mapper.get_mapped_category("NonExistent", "Anything")
        assert result is None


class TestClassifyHierarchy:

    def test_uses_mapping_first(self):
        m, t = _create_test_files()
        mapper = CategoryMapper(mapping_path=m, taxonomy_path=t)
        result = mapper.classify("Electronics", "Cameras", use_ai=False)
        assert result == "Technology > Photography"

    def test_fallback_when_no_mapping(self):
        m, t = _create_test_files()
        mapper = CategoryMapper(mapping_path=m, taxonomy_path=t)
        result = mapper.classify("Sports", "Running", use_ai=False)
        assert result == FALLBACK_MAP["Sports"]

    @patch("src.enrichment.category_mapper.openai_client")
    def test_ai_called_when_no_mapping(self, mock_openai):
        mock_openai.chat_text.return_value = "Sports & Leisure > Fitness"
        m, t = _create_test_files()
        mapper = CategoryMapper(mapping_path=m, taxonomy_path=t)
        result = mapper.classify("UnknownDept", "UnknownCat", use_ai=True)
        assert result == "Sports & Leisure > Fitness"
        mock_openai.chat_text.assert_called_once()


class TestFlattenPaths:

    def test_generates_leaf_paths(self):
        m, t = _create_test_files()
        mapper = CategoryMapper(mapping_path=m, taxonomy_path=t)
        assert "Technology > Audio" in mapper.valid_paths
        assert "Home & Garden > Kitchen" in mapper.valid_paths
        assert len(mapper.valid_paths) == 6
