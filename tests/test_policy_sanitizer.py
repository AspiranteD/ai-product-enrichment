"""Tests for the marketplace policy sanitizer."""
from src.enrichment.policy_sanitizer import sanitize_text, text_needs_sanitizing, has_risk_word


class TestSanitizeText:

    def test_satellite_receiver_replaced(self):
        raw = "Receptor satélite digital Full HD USB WiFi"
        out = sanitize_text(raw)
        assert "satélite" not in out.lower()
        assert "satelite" not in out.lower()
        assert "sintonizador" in out.lower() or "tdt" in out.lower()

    def test_logitech_receiver_unchanged(self):
        """'receptor' alone should NOT be replaced (Logitech, mouse dongles, etc.)."""
        raw = "Logitech USB Receptor Unifying negro"
        out = sanitize_text(raw)
        assert "receptor" in out.lower()

    def test_iptv_replaced(self):
        out = sanitize_text("Dispositivo IPTV streaming 4K")
        assert "iptv" not in out.lower()
        assert "televisión" in out.lower()

    def test_spy_camera_replaced(self):
        out = sanitize_text("Cámara espía WiFi HD 1080p")
        assert "espía" not in out.lower()
        assert "cámara" in out.lower()

    def test_jailbreak_removed(self):
        out = sanitize_text("iPhone 12 jailbreak desbloqueado")
        assert "jailbreak" not in out.lower()
        assert "libre" in out.lower()

    def test_title_truncation(self):
        long_title = "A" * 60
        out = sanitize_text(long_title, for_title=True)
        assert len(out) <= 50

    def test_empty_input(self):
        assert sanitize_text(None) == ""
        assert sanitize_text("") == ""
        assert sanitize_text("nan") == ""

    def test_android_tv_replaced(self):
        out = sanitize_text("Android TV Box 4K HDR")
        assert "android tv" not in out.lower()

    def test_exam_pinganillo_replaced(self):
        out = sanitize_text("Pinganillo para examen Bluetooth")
        assert "pinganillo" not in out.lower()
        assert "auricular" in out.lower()

    def test_multiple_spaces_collapsed(self):
        out = sanitize_text("Kodi  media  center  IPTV")
        assert "  " not in out


class TestTextNeedsSanitizing:

    def test_clean_text(self):
        assert text_needs_sanitizing("Auricular Bluetooth Sony") is False

    def test_risky_text(self):
        assert text_needs_sanitizing("Receptor satélite HD") is True

    def test_none_input(self):
        assert text_needs_sanitizing(None) is False


class TestHasRiskWord:

    def test_no_risk(self):
        assert has_risk_word("Normal product", "Clean description") is False

    def test_risk_in_second(self):
        assert has_risk_word("Clean title", "Decodificador HD") is True

    def test_all_none(self):
        assert has_risk_word(None, None) is False
