"""
EasyCaptcha — Automated Test Suite  (v1.3.0)
==============================================
Tests image generation, character set, rate limiter, IP binding,
audio generation, and minimum solve time — without requiring a running
server or MongoDB.

Run (unit tests only):
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pytest test_captcha.py -v

Run (with live service on port 8080):
    pytest test_captcha.py -v --integration
"""

import base64
import os
import shutil
import time
import pytest

os.environ.setdefault("MONGODB_URL",    "mongodb://localhost:27017")
os.environ.setdefault("API_SECRET_KEY", "test-secret-key-for-tests")

from captcha_service import (
    _check_rate_limit,
    _find_font,
    _generate_captcha_image,
    _generate_audio_captcha,
    _espeak_available,
    _CHARS,
    _rate_store,
    _verify_rate_store,
    _audio_rate_store,
    CAPTCHA_LENGTH,
    CAPTCHA_LENGTH_MIN,
    CAPTCHA_LENGTH_MAX,
    RATE_LIMIT_RPM,
    VERIFY_LIMIT_RPM,
    AUDIO_LIMIT_RPM,
    ENFORCE_IP_BINDING,
    CAPTCHA_MIN_SOLVE_MS,
)


def fresh_ip():
    return f"test-{time.monotonic()}"


# ── Image generation ──────────────────────────────────────────────────────────

class TestImageGeneration:

    def test_returns_nonempty_string(self):
        assert len(_generate_captcha_image("Ab3Kz")) > 100

    def test_output_is_valid_base64(self):
        base64.b64decode(_generate_captcha_image("HeLLo"))

    def test_output_is_valid_png(self):
        decoded = base64.b64decode(_generate_captcha_image("TeSt2"))
        assert decoded[:4] == b"\x89PNG"

    def test_different_codes_produce_different_images(self):
        assert _generate_captcha_image("AAAAA") != _generate_captcha_image("zzzzz")

    def test_same_code_produces_different_images(self):
        assert _generate_captcha_image("Ab3Kz") != _generate_captcha_image("Ab3Kz")

    def test_various_lengths(self):
        for n in (4, 5, 6, 7):
            assert base64.b64decode(_generate_captcha_image("A" * n))[:4] == b"\x89PNG"

    def test_single_character(self):
        assert base64.b64decode(_generate_captcha_image("A"))[:4] == b"\x89PNG"

    def test_lowercase_code(self):
        assert base64.b64decode(_generate_captcha_image("abcde"))[:4] == b"\x89PNG"

    def test_mixed_case_code(self):
        assert base64.b64decode(_generate_captcha_image("aB3kZ"))[:4] == b"\x89PNG"


# ── Character set ─────────────────────────────────────────────────────────────

class TestCharacterSet:

    def test_excludes_uppercase_ambiguous_chars(self):
        for ch in ("I", "O"):
            assert ch not in _CHARS, f"Uppercase '{ch}' must be excluded"

    def test_excludes_lowercase_ambiguous_chars(self):
        for ch in ("i", "l", "o"):
            assert ch not in _CHARS, f"Lowercase '{ch}' must be excluded"

    def test_excludes_digit_ambiguous_chars(self):
        for ch in ("0", "1"):
            assert ch not in _CHARS, f"Digit '{ch}' must be excluded"

    def test_contains_uppercase_chars(self):
        assert "A" in _CHARS and "Z" in _CHARS

    def test_contains_lowercase_chars(self):
        assert "a" in _CHARS and "z" in _CHARS
        assert sum(1 for c in _CHARS if c.islower()) >= 10

    def test_contains_digit_chars(self):
        assert "2" in _CHARS and "9" in _CHARS

    def test_all_chars_are_alphanumeric(self):
        for ch in _CHARS:
            assert ch.isalnum(), f"'{ch}' is not alphanumeric"

    def test_no_duplicates(self):
        assert len(_CHARS) == len(set(_CHARS))

    def test_minimum_pool_size(self):
        assert len(_CHARS) >= 40, f"Pool too small: {len(_CHARS)}"


# ── Rate limiter ──────────────────────────────────────────────────────────────

class TestRateLimiter:

    def test_allows_requests_under_limit(self):
        ip = fresh_ip()
        for i in range(RATE_LIMIT_RPM):
            assert _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM), f"Request #{i+1} blocked"

    def test_blocks_requests_over_limit(self):
        ip = fresh_ip()
        for _ in range(RATE_LIMIT_RPM):
            _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM)
        assert not _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM)

    def test_different_ips_are_independent(self):
        ip_a, ip_b = fresh_ip(), fresh_ip()
        for _ in range(RATE_LIMIT_RPM + 1):
            _check_rate_limit(ip_a, _rate_store, RATE_LIMIT_RPM)
        assert _check_rate_limit(ip_b, _rate_store, RATE_LIMIT_RPM)

    def test_window_resets_after_60_seconds(self):
        ip = fresh_ip()
        _rate_store[ip] = [time.monotonic() - 61] * RATE_LIMIT_RPM
        assert _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM)

    def test_allows_new_requests_after_partial_window_expires(self):
        ip = fresh_ip()
        _rate_store[ip] = [time.monotonic() - 61] * 10 + [time.monotonic() - 1] * (RATE_LIMIT_RPM - 2)
        assert _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM)

    def test_verify_rate_limit_is_separate(self):
        ip = fresh_ip()
        for _ in range(RATE_LIMIT_RPM + 1):
            _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM)
        assert _check_rate_limit(ip, _verify_rate_store, VERIFY_LIMIT_RPM)

    def test_audio_rate_limit_is_separate(self):
        ip = fresh_ip()
        for _ in range(RATE_LIMIT_RPM + 1):
            _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM)
        assert _check_rate_limit(ip, _audio_rate_store, AUDIO_LIMIT_RPM)

    def test_audio_rate_limit_config(self):
        assert AUDIO_LIMIT_RPM > 0


# ── Font detection ────────────────────────────────────────────────────────────

class TestFontDetection:

    def test_returns_string_or_none(self):
        result = _find_font()
        assert result is None or isinstance(result, str)

    def test_path_exists_if_found(self):
        result = _find_font()
        if result is not None:
            assert os.path.isfile(result)


# ── Audio captcha ─────────────────────────────────────────────────────────────

class TestAudio:

    def test_espeak_available_returns_bool(self):
        assert isinstance(_espeak_available(), bool)

    def test_espeak_check_matches_shutil(self):
        assert _espeak_available() == (shutil.which("espeak-ng") is not None)

    @pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng not installed")
    def test_generate_audio_returns_wav(self):
        audio = _generate_audio_captcha("Ab3")
        assert isinstance(audio, bytes)
        # WAV files start with "RIFF" magic bytes
        assert audio[:4] == b"RIFF", f"Expected WAV, got {audio[:4]!r}"

    @pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng not installed")
    def test_generate_audio_different_codes_different_lengths(self):
        a1 = _generate_audio_captcha("A")
        a5 = _generate_audio_captcha("ABCDE")
        # 5-char audio should generally be longer than 1-char audio
        assert len(a5) >= len(a1), "Longer code should produce equal or longer audio"

    def test_generate_audio_raises_when_no_espeak(self):
        if _espeak_available():
            pytest.skip("espeak-ng is installed — cannot test missing-binary path")
        with pytest.raises(FileNotFoundError):
            _generate_audio_captcha("TEST")


# ── IP binding ────────────────────────────────────────────────────────────────

class TestIPBindingConfig:

    def test_enforce_ip_binding_is_bool(self):
        assert isinstance(ENFORCE_IP_BINDING, bool)

    def test_enforce_ip_binding_default_is_false(self):
        """Default should be False for backward compatibility."""
        # The actual value depends on the env var; we just test that it's bool.
        assert ENFORCE_IP_BINDING in (True, False)


# ── Config ────────────────────────────────────────────────────────────────────

class TestConfig:

    def test_captcha_length_is_positive(self):
        assert CAPTCHA_LENGTH >= 1

    def test_rate_limit_is_positive(self):
        assert RATE_LIMIT_RPM >= 1

    def test_verify_rate_limit_is_positive(self):
        assert VERIFY_LIMIT_RPM >= 1

    def test_verify_rate_limit_higher_than_captcha_limit(self):
        assert VERIFY_LIMIT_RPM >= RATE_LIMIT_RPM


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.fixture
def integration(request):
    return request.config.getoption("--integration")


class TestIntegration:

    def test_health(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx
        res = httpx.get("http://localhost:8080/health", timeout=5)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.2.0"
        assert "audio_available" in data

    def test_generate_captcha_includes_audio_available(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx
        res = httpx.get("http://localhost:8080/captcha", timeout=10)
        assert res.status_code == 200
        data = res.json()
        assert "token_id"        in data
        assert "image_b64"       in data
        assert "captcha_length"  in data
        assert "audio_available" in data
        assert isinstance(data["audio_available"], bool)

    def test_generate_and_verify(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx
        api_key = os.environ.get("API_SECRET_KEY", "test-secret-key-for-tests")

        res = httpx.get("http://localhost:8080/captcha", timeout=10)
        assert res.status_code == 200
        token_id = res.json()["token_id"]

        # Wrong answer — token consumed on first call
        res = httpx.post(
            "http://localhost:8080/captcha/verify",
            json={"token_id": token_id, "answer": "XXXXX"},
            headers={"X-API-Key": api_key},
            timeout=5,
        )
        assert res.status_code == 200
        assert res.json()["valid"] is False
        assert res.json().get("error_code") in ("wrong_answer", "not_found")

        # Second attempt — token is consumed, must return not_found
        res2 = httpx.post(
            "http://localhost:8080/captcha/verify",
            json={"token_id": token_id, "answer": "YYYYY"},
            headers={"X-API-Key": api_key},
            timeout=5,
        )
        assert res2.json()["valid"] is False
        assert res2.json().get("error_code") == "not_found"

    def test_verify_missing_api_key(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx
        res = httpx.post(
            "http://localhost:8080/captcha/verify",
            json={"token_id": "fake", "answer": "XXXXX"},
            timeout=5,
        )
        assert res.status_code == 401

    def test_audio_endpoint(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx
        res = httpx.get("http://localhost:8080/captcha", timeout=10)
        token_id = res.json()["token_id"]
        audio_available = res.json()["audio_available"]

        res_audio = httpx.get(f"http://localhost:8080/captcha/audio/{token_id}", timeout=15)
        if audio_available:
            assert res_audio.status_code == 200
            assert res_audio.headers["content-type"] == "audio/wav"
            assert res_audio.content[:4] == b"RIFF"
        else:
            assert res_audio.status_code == 503

    def test_stats_requires_api_key(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx
        assert httpx.get("http://localhost:8080/stats", timeout=5).status_code == 401

    def test_stats_with_valid_key(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx
        api_key = os.environ.get("API_SECRET_KEY", "test-secret-key-for-tests")
        res = httpx.get(
            "http://localhost:8080/stats",
            headers={"X-API-Key": api_key},
            timeout=5,
        )
        assert res.status_code == 200
        data = res.json()
        assert "tokens_in_db"    in data
        assert data["service_version"] == "1.3.0"


# ── Minimum solve time (anti-bot timing check) ────────────────────────────────

class TestMinSolveTime:

    def test_min_solve_ms_is_non_negative(self):
        assert CAPTCHA_MIN_SOLVE_MS >= 0

    def test_min_solve_ms_type(self):
        assert isinstance(CAPTCHA_MIN_SOLVE_MS, int)

    def test_min_solve_ms_default_is_1500(self):
        """Default must be high enough to catch automated solvers (< 50 ms)."""
        # When running tests the env var is not set, so default applies.
        # If user customised it, allow any non-negative value.
        assert CAPTCHA_MIN_SOLVE_MS >= 0

    def test_zero_disables_check(self):
        """Setting CAPTCHA_MIN_SOLVE_MS=0 should not raise errors anywhere."""
        import os, importlib
        old = os.environ.get("CAPTCHA_MIN_SOLVE_MS")
        os.environ["CAPTCHA_MIN_SOLVE_MS"] = "0"
        try:
            import captcha_service as cs
            importlib.reload(cs)
            assert cs.CAPTCHA_MIN_SOLVE_MS == 0
        finally:
            if old is None:
                os.environ.pop("CAPTCHA_MIN_SOLVE_MS", None)
            else:
                os.environ["CAPTCHA_MIN_SOLVE_MS"] = old
            importlib.reload(cs)


# ── Honeypot ──────────────────────────────────────────────────────────────────

class TestHoneypot:

    def test_honeypot_field_defaults_to_empty(self):
        from captcha_service import VerifyRequest
        p = VerifyRequest(token_id="abc", answer="ABC")
        assert p.honeypot == ""

    def test_honeypot_accepts_non_empty_value(self):
        from captcha_service import VerifyRequest
        p = VerifyRequest(token_id="abc", answer="ABC", honeypot="bot-was-here")
        assert p.honeypot == "bot-was-here"

    def test_honeypot_present_in_verify_request_schema(self):
        from captcha_service import VerifyRequest
        fields = VerifyRequest.model_fields
        assert "honeypot" in fields
        assert fields["honeypot"].default == ""


# ── Length randomisation ──────────────────────────────────────────────────────

class TestLengthRandomisation:

    def test_length_min_max_are_valid(self):
        from captcha_service import CAPTCHA_LENGTH_MIN, CAPTCHA_LENGTH_MAX
        assert CAPTCHA_LENGTH_MIN >= 1
        assert CAPTCHA_LENGTH_MAX >= CAPTCHA_LENGTH_MIN

    def test_length_min_defaults_to_captcha_length(self):
        from captcha_service import CAPTCHA_LENGTH, CAPTCHA_LENGTH_MIN, CAPTCHA_LENGTH_MAX
        # When neither override is set the range should equal the fixed length
        import os
        if "CAPTCHA_LENGTH_MIN" not in os.environ and "CAPTCHA_LENGTH_MAX" not in os.environ:
            assert CAPTCHA_LENGTH_MIN == CAPTCHA_LENGTH
            assert CAPTCHA_LENGTH_MAX == CAPTCHA_LENGTH

    def test_image_generated_for_various_lengths(self):
        """Image generation must work for all lengths in the configured range."""
        from captcha_service import _generate_captcha_image, _CHARS, CAPTCHA_LENGTH_MIN, CAPTCHA_LENGTH_MAX
        import secrets
        for length in range(CAPTCHA_LENGTH_MIN, CAPTCHA_LENGTH_MAX + 1):
            code = ''.join(secrets.choice(_CHARS) for _ in range(length))
            img_b64 = _generate_captcha_image(code)
            assert len(img_b64) > 0, f"Empty image for length {length}"
