# EasyCaptcha — Project Memory

## Original Problem Statement
"Check all the codes make sure if it's working fine with proper testing it's kind of open source captcha I just stored in my repo for public use."

**Follow-up 1 (v1.1.0):** Fix all bugs, add wrong-answer feedback, reload button, anti-bot/anti-OCR security, lowercase characters, and all enhancements.

**Follow-up 2 (v1.2.0):** MongoDB auth, IP binding, Audio CAPTCHA (WCAG 2.1).

---

## Repository
https://github.com/ajaykumarvarma/EasyCaptcha

## Architecture
- `backend/captcha_service.py` — FastAPI service
- `frontend/ServerCaptcha.jsx` — React server-side component
- `frontend/CanvasCaptcha.jsx` — React client-side canvas component
- `backend/test_captcha.py` + `conftest.py` — Test suite (46 tests)
- `docs/index.html` — Live demo page
- `docker/docker-compose.yml` — Docker + MongoDB compose
- `docker/mongo-init.js` — MongoDB init script (creates captcha_svc user)

---

## What Was Implemented

### v1.1.0 (Bug fixes + Security hardening)
- [x] MongoDB unique index on token_id (O(1) lookup)
- [x] Rate limiter memory leak fixed + background cleanup task
- [x] Token consumed on wrong answer too (prevents brute-force)
- [x] Rate limiting on /captcha/verify endpoint
- [x] Mixed-case character pool (55 chars: upper+lower+digits, no i/l/o/I/O/0/1)
- [x] Font path cached at startup
- [x] Wave distortion + foreground noise (anti-OCR)
- [x] VerifyResponse.error_code for debugging
- [x] Better startup errors (_require_env)
- [x] Reload button in both components
- [x] Wrong-answer error UI with red message + icon
- [x] All GitHub placeholder URLs replaced
- [x] backend/.env.example and requirements-dev.txt added
- [x] Version: 1.1.0

### v1.3.0 (Security hardening + UX polish)
- [x] **Bug Fix:** Success message now correctly clears when user gets a new captcha via "Get a new code" button
- [x] **Security:** Minimum solve time check (`CAPTCHA_MIN_SOLVE_MS=1500`) — rejects answers arriving in < 1.5 s (bot timing attack mitigation)
- [x] **Security:** Enhanced server image generation — 180 dots (was 130), 8 foreground lines (was 5), arc noise over characters, variable character spacing ±3px, tighter rotation ±33°
- [x] **Security:** Enhanced canvas rendering — 90 dots (was 60), 14 bezier lines (was 10), 3 arc noise passes, 6 foreground lines (was 4), variable char offsets
- [x] **Security (Bug fix):** `CanvasCaptcha.jsx` `validate()` was using `.toUpperCase()` comparison (case-insensitive!) — fixed to strict `===` comparison
- [x] **UX:** Character progress dots (●●●○○) below input in all 3 frontends
- [x] **UX:** Auto-validate 700ms after all characters typed (canvas demo only)
- [x] New `error_code: "too_fast"` in `VerifyResponse`
- [x] New `CAPTCHA_MIN_SOLVE_MS` env var (0 = disabled)
- [x] Version bumped to 1.3.0 across all files
- [x] **Security:** Honeypot hidden field (`name="website"`) in `ServerCaptcha.jsx` and server captcha demo — checked client-side (silent block) and backend (early `bot_suspected` rejection before any DB hit)
- [x] New `error_code: "bot_suspected"` in `VerifyResponse`
- [x] `onReady` payload now includes `honeypot` field: `{ tokenId, answer, honeypot }`
- [x] **Feature:** Per-request length randomisation — `CAPTCHA_LENGTH_MIN` / `CAPTCHA_LENGTH_MAX` env vars on backend; `minLength`/`maxLength` props on `CanvasCaptcha`; dynamic dots + maxLength in all demos; 47 tests pass
- [x] **Docs:** Comprehensive HTTPS/TLS section in README — Caddy (automatic TLS), nginx + Certbot, Docker Compose nginx, forwarded-IP + IP-binding notes
- [x] **MongoDB authentication in docker-compose:**
  - Root admin: `MONGO_ROOT_USERNAME`/`MONGO_ROOT_PASSWORD`
  - App user: `captcha_svc` (readWrite on easycaptcha db only) — least privilege
  - `docker/mongo-init.js` creates captcha_svc on first start
  - `docker/.env.example` — template for Docker secrets
  - healthcheck uses `db.adminCommand('ping')` (works without auth)
- [x] **IP Binding:**
  - Token stores originating IP at generation time
  - `ENFORCE_IP_BINDING=true` env var enables strict mode
  - `VerifyRequest.client_ip` optional field — integrator passes end-user IP
  - New error codes: `ip_missing` | `ip_mismatch`
  - Backward-compatible (default: false)
- [x] **Audio CAPTCHA (WCAG 2.1 SC 1.1.1):**
  - Backend: `GET /captcha/audio/{token_id}` → WAV via espeak-ng
  - `CaptchaResponse.audio_available` tells frontend if espeak-ng is installed
  - `AUDIO_LIMIT_PER_MIN` rate limiting (default 20/min)
  - espeak-ng added to Dockerfile
  - `ServerCaptcha.jsx`: speaker button plays WAV from backend
  - `CanvasCaptcha.jsx`: speaker button uses Web Speech API (browser-native, offline)
  - Both: Stop button to cancel audio mid-playback
  - Graceful degradation when unavailable (button hidden, no errors)
- [x] Version: 1.2.0
- [x] 37 tests pass (9 skipped: audio tests need espeak-ng, integration tests need live service)

---

## Test Results (v1.3.0)
```
41 passed, 9 skipped
- Audio WAV tests: skip when espeak-ng not installed (installed in Docker)
- Integration tests: skip without --integration flag + live server
```

---

## v1.4.0 — Security hardening (2025)
- [x] **HMAC-SHA256 answer hashing** — `code_hash` field stored in MongoDB (keyed with API_SECRET_KEY). DB dump without the app secret doesn't reveal answers.
- [x] **Constant-time comparison** — `hmac.compare_digest()` for both API key and answer hash comparison. Prevents timing-oracle attacks.
- [x] **Multi-font random selection** — `_find_fonts()` scans 14 font paths, returns all available. Up to 6 bold fonts (sans-serif, serif, mono) picked randomly per character. `_FONT_PATHS` replaces single `_FONT_PATH`. Backward-compat `_find_font()` preserved.
- [x] **Expanded random color palette** — 14 colors (was 6), `rng.choice(_COLORS)` per character (was `_COLORS[i % len]`).
- [x] **Paste blocking** — `onPaste={e => e.preventDefault()}` in `ServerCaptcha.jsx`, `CanvasCaptcha.jsx`, and `addEventListener('paste')` in `docs/index.html`.
- [x] Tests: **67 passed, 9 skipped** (4 new test classes: `TestAnswerHashing`, `TestMultiFontSelection`, `TestRandomColorPalette`, `TestPasteBlocking`)
- [x] README: v1.4.0 changelog, updated security notes table, production checklist, test count

## Test Results (v1.4.0)
```
67 passed, 9 skipped
```

---

## v1.5.0 — Analytics endpoint (2025)
- [x] `GET /stats/detailed?hours=N` — rolling-window analytics with per-rejection-type breakdown
- [x] `_log_event(outcome)` coroutine logs every verify outcome to `captcha_events` collection
- [x] MongoDB TTL index auto-purges events after `STATS_RETENTION_DAYS` (default 7 days)
- [x] `DetailedStatsResponse`: `window_hours`, `total_attempts`, `solved`, `solve_rate`, `rejections`, `top_rejection`, `retention_days`, `service_version`
- [x] `hours` query param: 1–168 (validated); `bot_suspected` uses `asyncio.create_task()` (fire-and-forget)
- [x] Tests: **79 passed, 9 skipped** (`TestDetailedStats` — 12 new tests with mocked ASGI endpoint tests)
- [x] README: `GET /stats/detailed` API reference with full response example and outcome types table
- [x] `.env.example`: `STATS_RETENTION_DAYS=7` documented
- [x] `pytest.ini` added with `asyncio_mode = auto`

## Test Results (v1.5.0)
```
79 passed, 9 skipped
```

---

## Prioritized Backlog

### P1 (Important)
- Redis-backed rate limiter (in-memory store resets on restart, not shared across instances)

### P2 (Nice to have)
- Math CAPTCHA variant ("What is 4 + 7?")
- Animated loading skeleton in React components
- Cypress/Playwright E2E tests against the demo page
- Behavioral analytics: keystroke timing + mouse interaction scoring

### P3 (Future)
- Admin dashboard UI wrapping `GET /stats/detailed` (visualize solve rates and rejection charts)
- Multi-instance Docker Swarm / Kubernetes deployment notes