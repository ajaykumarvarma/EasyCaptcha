"""
EasyCaptcha — Automated Test Suite
====================================
Tests the core functions of captcha_service.py without requiring a running server
or a real MongoDB instance.

Run with:
    pip install -r requirements.txt
    pip install pytest httpx  # or: pip install -r requirements-dev.txt
    pytest test_captcha.py -v

For full integration tests (requires a running service on port 8080):
    pytest test_captcha.py -v --integration
"""

import base64
import os
import time
import pytest

# Set required env vars before importing the service module
os.environ.setdefault("MONGODB_URL",    "mongodb://localhost:27017")
os.environ.setdefault("API_SECRET_KEY", "test-secret-key-for-tests")

# Import after env vars are set
from captcha_service import (
    _check_rate_limit,
    _find_font,
    _generate_captcha_image,
    _CHARS,
    _rate_store,
    _verify_rate_store,
    CAPTCHA_LENGTH,
    RATE_LIMIT_RPM,
    VERIFY_LIMIT_RPM,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def fresh_ip():
    """Return a unique IP string so each test gets a clean rate-limit slate."""
    return f"test-{time.monotonic()}"


# ── Image generation ──────────────────────────────────────────────────────────

class TestImageGeneration:

    def test_returns_nonempty_string(self):
        result = _generate_captcha_image("Ab3Kz")
        assert isinstance(result, str)
        assert len(result) > 100, "Image string is suspiciously short"

    def test_output_is_valid_base64(self):
        result = _generate_captcha_image("HeLLo")
        try:
            decoded = base64.b64decode(result)
        except Exception as exc:
            pytest.fail(f"Result is not valid base64: {exc}")
        assert len(decoded) > 0

    def test_output_is_valid_png(self):
        result = _generate_captcha_image("TeSt2")
        decoded = base64.b64decode(result)
        # PNG magic bytes: \x89PNG
        assert decoded[:4] == b"\x89PNG", (
            f"Expected PNG magic bytes, got {decoded[:4]!r}"
        )

    def test_different_codes_produce_different_images(self):
        img1 = _generate_captcha_image("AAAAA")
        img2 = _generate_captcha_image("zzzzz")
        assert img1 != img2, "Different codes must produce different images"

    def test_same_code_produces_different_images(self):
        """Each call should be unique because of random noise/rotation."""
        img1 = _generate_captcha_image("Ab3Kz")
        img2 = _generate_captcha_image("Ab3Kz")
        assert img1 != img2, (
            "Same code called twice should produce different images (random noise)"
        )

    def test_various_lengths(self):
        for length in (4, 5, 6, 7):
            code = "A" * length
            result = _generate_captcha_image(code)
            decoded = base64.b64decode(result)
            assert decoded[:4] == b"\x89PNG", f"Failed for length {length}"

    def test_single_character(self):
        result = _generate_captcha_image("A")
        decoded = base64.b64decode(result)
        assert decoded[:4] == b"\x89PNG"

    def test_lowercase_code(self):
        """Mixed-case codes must render correctly."""
        result = _generate_captcha_image("abcde")
        decoded = base64.b64decode(result)
        assert decoded[:4] == b"\x89PNG"

    def test_mixed_case_code(self):
        result = _generate_captcha_image("aB3kZ")
        decoded = base64.b64decode(result)
        assert decoded[:4] == b"\x89PNG"


# ── Character set ─────────────────────────────────────────────────────────────

class TestCharacterSet:

    def test_excludes_uppercase_ambiguous_chars(self):
        for ch in ("I", "O"):
            assert ch not in _CHARS, (
                f"Uppercase '{ch}' must be excluded (visually ambiguous)"
            )

    def test_excludes_lowercase_ambiguous_chars(self):
        for ch in ("i", "l", "o"):
            assert ch not in _CHARS, (
                f"Lowercase '{ch}' must be excluded (visually ambiguous: looks like 1, 1, or 0)"
            )

    def test_excludes_digit_ambiguous_chars(self):
        for ch in ("0", "1"):
            assert ch not in _CHARS, (
                f"Digit '{ch}' must be excluded (visually ambiguous)"
            )

    def test_contains_uppercase_chars(self):
        assert "A" in _CHARS
        assert "Z" in _CHARS

    def test_contains_lowercase_chars(self):
        """Pool must include lowercase letters for increased anti-OCR strength."""
        assert "a" in _CHARS
        assert "z" in _CHARS
        lowercase_count = sum(1 for c in _CHARS if c.islower())
        assert lowercase_count >= 10, (
            f"Too few lowercase chars ({lowercase_count}); need at least 10"
        )

    def test_contains_digit_chars(self):
        assert "2" in _CHARS
        assert "9" in _CHARS

    def test_all_chars_are_alphanumeric(self):
        for ch in _CHARS:
            assert ch.isalnum(), f"'{ch}' is not alphanumeric"

    def test_no_duplicates(self):
        assert len(_CHARS) == len(set(_CHARS)), "CAPTCHA_CHARS contains duplicate characters"

    def test_minimum_pool_size(self):
        assert len(_CHARS) >= 40, (
            f"Character pool too small ({len(_CHARS)}); mixed-case pool should have at least 40"
        )


# ── Rate limiter ──────────────────────────────────────────────────────────────

class TestRateLimiter:

    def test_allows_requests_under_limit(self):
        ip = fresh_ip()
        for i in range(RATE_LIMIT_RPM):
            assert _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM), \
                f"Should allow request #{i + 1}"

    def test_blocks_requests_over_limit(self):
        ip = fresh_ip()
        for _ in range(RATE_LIMIT_RPM):
            _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM)
        # Next one must be blocked
        assert not _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM), (
            "Should block request that exceeds RATE_LIMIT_RPM"
        )

    def test_different_ips_are_independent(self):
        ip_a = fresh_ip()
        ip_b = fresh_ip()
        # Exhaust ip_a
        for _ in range(RATE_LIMIT_RPM + 1):
            _check_rate_limit(ip_a, _rate_store, RATE_LIMIT_RPM)
        # ip_b must still be allowed
        assert _check_rate_limit(ip_b, _rate_store, RATE_LIMIT_RPM), \
            "Rate limit from one IP must not affect another"

    def test_window_resets_after_60_seconds(self):
        """
        Simulate time passing by manually aging the stored timestamps.
        This avoids actually sleeping for 60 seconds.
        """
        ip = fresh_ip()
        # Fill the store with timestamps from 61 seconds ago
        old_time = time.monotonic() - 61
        _rate_store[ip] = [old_time] * RATE_LIMIT_RPM

        assert _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM), (
            "Requests older than 60 s should fall outside the sliding window"
        )

    def test_allows_new_requests_after_partial_window_expires(self):
        ip = fresh_ip()
        old_time    = time.monotonic() - 61
        recent_time = time.monotonic() - 1
        _rate_store[ip] = [old_time] * 10 + [recent_time] * (RATE_LIMIT_RPM - 2)
        assert _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM), \
            "Should allow requests when old ones expired"

    def test_verify_rate_limit_is_separate(self):
        """Verify endpoint has its own independent rate limit store."""
        ip = fresh_ip()
        # Fill /captcha rate limit
        for _ in range(RATE_LIMIT_RPM + 1):
            _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM)
        # /captcha/verify should still be allowed for same IP
        assert _check_rate_limit(ip, _verify_rate_store, VERIFY_LIMIT_RPM), \
            "Verify rate limit store must be independent of captcha rate limit store"


# ── Font detection ────────────────────────────────────────────────────────────

class TestFontDetection:

    def test_returns_string_or_none(self):
        result = _find_font()
        assert result is None or isinstance(result, str)

    def test_path_exists_if_found(self):
        result = _find_font()
        if result is not None:
            assert os.path.isfile(result), f"Font path returned does not exist: {result}"


# ── Config ────────────────────────────────────────────────────────────────────

class TestConfig:

    def test_captcha_length_is_positive(self):
        assert CAPTCHA_LENGTH >= 1

    def test_rate_limit_is_positive(self):
        assert RATE_LIMIT_RPM >= 1

    def test_verify_rate_limit_is_positive(self):
        assert VERIFY_LIMIT_RPM >= 1

    def test_verify_rate_limit_higher_than_captcha_limit(self):
        """Verify limit should be higher than captcha limit (backend-to-backend calls)."""
        assert VERIFY_LIMIT_RPM >= RATE_LIMIT_RPM, (
            "VERIFY_LIMIT_RPM should be >= RATE_LIMIT_RPM "
            "(verify is a backend call and may be invoked frequently)"
        )


# ── Integration tests (skipped by default) ───────────────────────────────────
#
# These require a running EasyCaptcha service (and MongoDB) on port 8080.
# Run with:   pytest test_captcha.py -v --integration
#


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
        assert res.json()["status"] == "ok"
        assert res.json()["version"] == "1.1.0"

    def test_generate_and_verify(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx

        api_key = os.environ.get("API_SECRET_KEY", "test-secret-key-for-tests")

        # Generate
        res = httpx.get("http://localhost:8080/captcha", timeout=10)
        assert res.status_code == 200
        data = res.json()
        assert "token_id"       in data
        assert "image_b64"      in data
        assert "captcha_length" in data
        assert data["captcha_length"] >= 1

        token_id = data["token_id"]

        # Wrong answer — token is consumed on first call (correct OR wrong)
        res = httpx.post(
            "http://localhost:8080/captcha/verify",
            json={"token_id": token_id, "answer": "XXXXX"},
            headers={"X-API-Key": api_key},
            timeout=5,
        )
        assert res.status_code == 200
        assert res.json()["valid"] is False
        # error_code tells integrator why it failed (for debugging only)
        assert res.json().get("error_code") in ("wrong_answer", "not_found")

        # Second attempt with same token must fail — token was consumed above
        res2 = httpx.post(
            "http://localhost:8080/captcha/verify",
            json={"token_id": token_id, "answer": "YYYYY"},
            headers={"X-API-Key": api_key},
            timeout=5,
        )
        assert res2.status_code == 200
        assert res2.json()["valid"] is False
        # Token is now consumed — should return not_found
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

    def test_stats_requires_api_key(self, integration):
        if not integration:
            pytest.skip("Pass --integration to run live tests")
        import httpx
        res = httpx.get("http://localhost:8080/stats", timeout=5)
        assert res.status_code == 401

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
        assert "active_unused"   in data
        assert "verified"        in data
        assert "service_version" in data
        assert data["service_version"] == "1.1.0"
