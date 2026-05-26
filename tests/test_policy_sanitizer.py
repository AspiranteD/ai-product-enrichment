"""Tests for the marketplace policy sanitizer."""
import pytest
from src.enrichment.policy_sanitizer import (
    sanitize_text,
    text_needs_sanitizing,
    has_risk_word,
)


class TestSanitizeText:
    """Verifies replacement rules and edge cases."""

    def test_satellite_receiver_replaced(self):
        assert sanitize_text("Receptor satélite HD") == "sintonizador TDT HD"

    def test_decoder_replaced(self):
        assert sanitize_text("Decodificador digital") == "sintonizador digital"

    def test_satellite_standalone_replaced(self):
        assert sanitize_text("Antena satélite parabólica") == "Antena TDT parabólica"

    def test_iptv_replaced(self):
        assert sanitize_text("Reproductor IPTV 4K") == "Reproductor televisión 4K"

    def test_kodi_removed(self):
        assert sanitize_text("Con Kodi instalado") == "Con instalado"

    def test_android_tv_replaced(self):
        # "Android TV" → "Smart TV", then "TV Box" triggers but "TV" already consumed
        assert sanitize_text("Android TV Box 4K") == "Smart reproductor 4K"

    def test_tv_box_replaced(self):
        assert sanitize_text("TV Box Android") == "reproductor Android"

    def test_emulator_replaced(self):
        assert sanitize_text("Emulador de juegos retro") == "software juegos de juegos retro"

    def test_spy_camera_replaced(self):
        assert sanitize_text("Cámara espía WiFi") == "cámara mini WiFi"

    def test_hidden_camera_replaced(self):
        assert sanitize_text("Cámara oculta miniatura") == "cámara compacta miniatura"

    def test_spy_watch_replaced(self):
        assert sanitize_text("Reloj espía con grabación") == "reloj cámara con grabación"

    def test_exam_earpiece_full(self):
        text = "Pinganillo bluetooth mini invisible para examen"
        assert sanitize_text(text) == "auricular bluetooth mini"

    def test_exam_earpiece_short(self):
        assert sanitize_text("Pinganillo para examen") == "auricular bluetooth"

    def test_earpiece_generic(self):
        assert sanitize_text("Pinganillo inalámbrico") == "auricular bluetooth inalámbrico"

    def test_unlocked_phone(self):
        assert sanitize_text("iPhone desbloqueado") == "iPhone libre"

    def test_gps_car_tracker(self):
        assert sanitize_text("Localizador GPS coche") == "tracker GPS vehículo"

    def test_hacked_removed(self):
        # "hackeada" matches hack(eado|er)? pattern
        assert sanitize_text("Consola hackeado") == "Consola"

    def test_hacked_variant_removed(self):
        assert sanitize_text("Consola hacker mod") == "Consola mod"

    def test_pirated_removed(self):
        assert sanitize_text("Software pirateado") == "Software"

    def test_dvb_s_replaced(self):
        assert sanitize_text("Sintonizador DVB-S") == "Sintonizador DVB-T2"

    def test_tester_replaced(self):
        assert sanitize_text("Tester de voltaje") == "comprobador de voltaje"

    def test_gas_bottle_replaced(self):
        assert sanitize_text("Bombona gas butano") == "bombona butano"

    def test_clean_text_unchanged(self):
        text = "Aspiradora Dyson V15 inalámbrica"
        assert sanitize_text(text) == text

    def test_none_returns_empty(self):
        assert sanitize_text(None) == ""

    def test_nan_returns_empty(self):
        assert sanitize_text("nan") == ""

    def test_none_string_returns_empty(self):
        assert sanitize_text("None") == ""

    def test_empty_string_returns_empty(self):
        assert sanitize_text("") == ""

    def test_double_spaces_collapsed(self):
        result = sanitize_text("Con Kodi y IPTV integrado")
        assert "  " not in result

    def test_case_insensitive(self):
        assert "satélite" not in sanitize_text("RECEPTOR SATÉLITE Premium").lower()


class TestTitleTruncation:
    """Verifies word-boundary truncation for titles."""

    def test_short_title_unchanged(self):
        title = "Auricular bluetooth mini"
        assert sanitize_text(title, for_title=True) == title

    def test_long_title_truncated_at_word(self):
        title = "X" * 30 + " " + "Y" * 25
        result = sanitize_text(title, for_title=True)
        assert len(result) <= 50
        assert not result.endswith(" ")

    def test_exactly_50_chars_unchanged(self):
        title = "A" * 50
        assert sanitize_text(title, for_title=True) == title

    def test_51_chars_truncated(self):
        title = "word " * 11  # 55 chars
        result = sanitize_text(title, for_title=True)
        assert len(result) <= 50


class TestTextNeedsSanitizing:
    """Tests the detection of flagged terms."""

    def test_flagged_text_detected(self):
        assert text_needs_sanitizing("Receptor satélite HD") is True

    def test_clean_text_not_flagged(self):
        assert text_needs_sanitizing("Aspiradora robot Roomba") is False

    def test_none_not_flagged(self):
        assert text_needs_sanitizing(None) is False


class TestHasRiskWord:
    """Tests multi-text risk detection."""

    def test_risk_in_first_text(self):
        assert has_risk_word("Decodificador HD", "Aspiradora") is True

    def test_risk_in_second_text(self):
        assert has_risk_word("Aspiradora", "TV Box 4K") is True

    def test_no_risk(self):
        assert has_risk_word("Aspiradora", "Robot cocina") is False

    def test_all_none(self):
        assert has_risk_word(None, None) is False

    def test_mixed_none_and_risk(self):
        assert has_risk_word(None, "IPTV player") is True
