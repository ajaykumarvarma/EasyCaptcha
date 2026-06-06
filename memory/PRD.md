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
- [x] 41 tests pass (was 37)
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

## Config Reference (v1.2.0)
| Env Var | Default | Description |
|---|---|---|
| MONGODB_URL | required | MongoDB connection string |
| API_SECRET_KEY | required | Secret for X-API-Key header |
| DB_NAME | easycaptcha | Database name |
| ALLOWED_ORIGINS | * | CORS origins |
| TOKEN_TTL_MINUTES | 5 | Token expiry |
| RATE_LIMIT_PER_MIN | 15 | GET /captcha limit/IP/min |
| VERIFY_LIMIT_PER_MIN | 60 | POST /captcha/verify limit/IP/min |
| AUDIO_LIMIT_PER_MIN | 20 | GET /captcha/audio limit/IP/min |
| CAPTCHA_LENGTH | 5 | Chars per challenge |
| ENFORCE_IP_BINDING | false | Reject verify if client_ip mismatch |
| LOG_LEVEL | INFO | DEBUG/INFO/WARNING/ERROR |

## Docker Secrets (docker/.env.example)
| Var | Purpose |
|---|---|
| MONGO_ROOT_USERNAME | MongoDB root admin user |
| MONGO_ROOT_PASSWORD | MongoDB root admin password |
| MONGO_CAPTCHA_PASSWORD | captcha_svc app user password |
| API_SECRET_KEY | EasyCaptcha API secret |
| ALLOWED_ORIGINS | CORS whitelist |
| ENFORCE_IP_BINDING | IP binding toggle |

---

## Prioritized Backlog

### P1 (Important)
- HTTPS/TLS documentation for production reverse proxy (nginx/caddy)
- Redis-backed rate limiter (current in-memory resets on restart)

### P2 (Nice to have)
- Math captcha variant
- Animated loading skeleton in React components
- `CAPTCHA_LENGTH` per-request randomisation (4-6 chars)
- Cypress/Playwright end-to-end tests against the demo page

## Config Reference (v1.3.0)
| Env Var | Default | Description |
|---|---|---|
| MONGODB_URL | required | MongoDB connection string |
| API_SECRET_KEY | required | Secret for X-API-Key header |
| DB_NAME | easycaptcha | Database name |
| ALLOWED_ORIGINS | * | CORS origins |
| TOKEN_TTL_MINUTES | 5 | Token expiry |
| RATE_LIMIT_PER_MIN | 15 | GET /captcha limit/IP/min |
| VERIFY_LIMIT_PER_MIN | 60 | POST /captcha/verify limit/IP/min |
| AUDIO_LIMIT_PER_MIN | 20 | GET /captcha/audio limit/IP/min |
| CAPTCHA_LENGTH | 5 | Chars per challenge |
| CAPTCHA_MIN_SOLVE_MS | 1500 | Min ms to solve (0=off) — anti-bot timing check |
| ENFORCE_IP_BINDING | false | Reject verify if client_ip mismatch |
| LOG_LEVEL | INFO | DEBUG/INFO/WARNING/ERROR |
