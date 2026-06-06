# EasyCaptcha — Project Memory

## Original Problem Statement
"Check all the codes make sure if it's working fine with proper testing it's kind of open source captcha I just stored in my repo for public use. They should be directly able to integrate in their website forms. Could you please check for any possible bugs wrong logics errors and proper exception handling?"

**Follow-up:** Fix all bugs, add wrong-answer feedback, reload button, anti-bot/anti-OCR security, lowercase characters, and all enhancements from review.

---

## Repository
https://github.com/ajaykumarvarma/EasyCaptcha

## Architecture
- **backend/captcha_service.py** — FastAPI service (token generation, verification, stats)
- **frontend/ServerCaptcha.jsx** — React drop-in component (server-side variant)
- **frontend/CanvasCaptcha.jsx** — React drop-in component (client-side canvas variant)
- **backend/test_captcha.py** + **conftest.py** — Test suite
- **docs/index.html** — Live demo page
- **docker/docker-compose.yml** — Docker + MongoDB compose

---

## What Was Implemented (June 2026 — v1.1.0)

### Backend (captcha_service.py)
- [x] **MongoDB unique index on `token_id`** — O(1) lookup instead of O(n) full-scan
- [x] **Rate limiter memory leak fixed** — plain dict (not defaultdict), background asyncio cleanup task every 5 min
- [x] **Token consumed on ANY verify call** (correct OR wrong) — prevents brute-force guessing
- [x] **Rate limiting added to /captcha/verify** — 60 req/min/IP via `VERIFY_LIMIT_PER_MIN`
- [x] **Mixed-case character pool** — 55 chars: ABCDEF...XYZ + abcdef...xyz (no i/l/o) + 23456789 — defeats uppercase OCR solvers
- [x] **Font path cached at startup** — no per-request filesystem probes
- [x] **Wave distortion** — sinusoidal row-shift breaks OCR character segmentation
- [x] **Foreground noise lines** — drawn OVER characters, not just background
- [x] **VerifyResponse.error_code** — "not_found" | "expired" | "already_used" | "wrong_answer" for integrator debugging
- [x] **Better startup errors** — `_require_env()` raises RuntimeError with clear message instead of bare KeyError
- [x] **Version bumped to 1.1.0**

### Frontend (ServerCaptcha.jsx)
- [x] **onReady ref pattern** — eliminates re-render loops when parent passes inline function
- [x] **Reload button** — with disabled state during loading, hover effect
- [x] **Mixed-case input** — removed forced uppercase, regex allows `[^A-Za-z0-9]`
- [x] **Wrong-answer error UI** — icon + red message with proper error display
- [x] **Input disabled during loading** — prevents submitting before captcha loads

### Frontend (CanvasCaptcha.jsx)
- [x] **Mixed-case characters** — `CAPTCHA_CHARS` expanded to 55 chars
- [x] **Case-insensitive comparison fix** — `input.toUpperCase() === captchaRef.current.toUpperCase()`
- [x] **Foreground noise lines** — 4 lines drawn over characters in canvas
- [x] **Wrong-answer error UI** — icon + red message
- [x] **Reload button** — "Get a new code" link

### Docs (docs/index.html)
- [x] **Live demo URL** — replaced all `your-username` placeholders with `ajaykumarvarma`
- [x] **Canvas CHARS** — updated to mixed-case pool
- [x] **Case-insensitive validation** — `input.toUpperCase() === canvasCode.toUpperCase()`
- [x] **Foreground noise** — added to refreshCanvas() demo
- [x] **ServerCaptcha verify message** — explains backend-only requirement clearly

### New Files
- [x] **backend/.env.example** — template with all config options documented
- [x] **backend/requirements-dev.txt** — pytest, httpx for running tests

### README
- [x] Replaced placeholder GitHub URLs with actual repo URL

### Tests (test_captcha.py)
- [x] **30 tests pass** (5 integration tests skip without live server)
- [x] New tests: mixed-case image generation, lowercase chars validation, verify rate limit isolation
- [x] Updated assertions for token-consumed-on-wrong-answer behavior
- [x] Updated `TestCharacterSet` to check lowercase included and ambiguous lowercase excluded

---

## Test Results
```
30 passed, 5 skipped (integration — need live service)
```

---

## Prioritized Backlog

### P0 (Blocking)
- None — all critical bugs fixed

### P1 (Important)
- MongoDB auth in docker-compose (currently unauthenticated)
- HTTPS/TLS config documentation for production
- IP binding: bind token to originating IP at generation time, reject cross-IP verify

### P2 (Nice to have)
- Redis-backed rate limiter (current in-memory resets on restart)
- Math captcha variant (addition/subtraction)
- Audio captcha alternative for accessibility
- `CAPTCHA_LENGTH` per-request randomisation (e.g., 4–6 chars)

---

## Config Reference (v1.1.0)
| Env Var | Default | Description |
|---|---|---|
| MONGODB_URL | required | MongoDB connection string |
| API_SECRET_KEY | required | Secret for /captcha/verify X-API-Key |
| DB_NAME | easycaptcha | MongoDB database name |
| ALLOWED_ORIGINS | * | Comma-separated CORS origins |
| TOKEN_TTL_MINUTES | 5 | Minutes until token expires |
| RATE_LIMIT_PER_MIN | 15 | Max GET /captcha per IP/min |
| VERIFY_LIMIT_PER_MIN | 60 | Max POST /captcha/verify per IP/min |
| CAPTCHA_LENGTH | 5 | Characters per challenge |
| LOG_LEVEL | INFO | DEBUG/INFO/WARNING/ERROR |
