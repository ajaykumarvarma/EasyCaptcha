# Legacy Captcha v1 — Server-side Image Captcha

**Status:** Replaced by Cloudflare Turnstile (v2)
**Date Archived:** June 2026

## What was v1?

A custom-built, fully in-house captcha system with two variants:

### 1. `ServerCaptcha` (auth flows)
- Backend generated a random 5-character code → stored in `captcha_tokens` MongoDB collection
- Rendered the code as a distorted PNG image via PIL → returned as base64
- Frontend displayed the image; user typed the code into an input
- Backend verified: token + typed answer, one-time use, 5-minute TTL
- Used on: Login, Signup, Forgot Password

### 2. `CanvasCaptcha` (submit tool page)
- Purely client-side canvas drawing — code generated and verified in the browser
- **No server-side verification** — this was the main weakness
- Used on: Submit Tool page

## Files in this archive

| File | Description |
|------|-------------|
| `auth_helpers_captcha_verify.py` | `_verify_captcha(token_id, answer)` helper |
| `auth_router_captcha_endpoint.py` | `GET /auth/captcha` endpoint (generates image) |
| `ServerCaptcha_component.jsx` | React component used in auth pages |
| `CanvasCaptcha_component.jsx` | Client-side canvas captcha component |
| `models_captcha_fields.py` | Old Pydantic models with `captcha_token_id` + `captcha_answer` |

## Why replaced?

1. **Limited bot resistance** — PIL-distorted images are easily solvable by modern OCR/ML models
2. **No IP binding** — same token could be solved from any IP and replayed
3. **Slow UX** — required a server roundtrip just to get the image
4. **Canvas captcha had zero server-side security**

## Replacement: Cloudflare Turnstile (v2)

- Site Key: stored in `frontend/.env` as `REACT_APP_CF_TURNSTILE_SITE_KEY`
- Secret Key: stored in `backend/.env` as `CF_TURNSTILE_SECRET`
- Token verified server-side via `https://challenges.cloudflare.com/turnstile/v0/siteverify`
- IP binding: `captcha_sessions` collection binds session_id to originating IP
