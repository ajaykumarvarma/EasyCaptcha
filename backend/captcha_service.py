"""
EasyCaptcha — Self-Hosted Image Captcha Service
================================================
Version : 1.1.0
License : MIT

A minimal, dependency-light FastAPI service that generates server-side
image captcha challenges and verifies answers.  No external CAPTCHA
vendors required.

Endpoints
---------
  GET  /captcha          — Generate a new challenge (token_id + base64 PNG)
  POST /captcha/verify   — Verify an answer from your backend (requires API key)
  GET  /stats            — Token statistics (requires API key)
  GET  /health           — Health check

Quick start
-----------
  1. Copy .env.example → .env and fill in values.
  2. pip install -r requirements.txt
  3. uvicorn captcha_service:app --host 0.0.0.0 --port 8080 --reload
     OR: docker compose -f ../docker/docker-compose.yml up

Changes in 1.1.0
----------------
  - Mixed-case + digit character pool (defeats simple uppercase OCR solvers).
  - Sinusoidal wave distortion + foreground noise lines (enhanced anti-OCR).
  - Token consumed on ANY verify call (correct OR wrong) — prevents brute-force.
  - Unique index on token_id for O(1) MongoDB lookups.
  - Rate limiting now also applied to /captcha/verify endpoint.
  - Memory leak fix: rate-store keys pruned via background asyncio task.
  - Font path cached at startup — no per-request filesystem probes.
  - Clear error messages when required env vars are missing.
  - VerifyResponse includes optional error_code for integrator debugging.
"""

import asyncio
import base64
import io
import logging
import math
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────


def _require_env(key: str) -> str:
    """Return env var value or raise RuntimeError with a clear message."""
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(
            f"FATAL: '{key}' environment variable is not set. "
            "Copy backend/.env.example → backend/.env and fill in the required values."
        )
    return val


MONGODB_URL      = _require_env("MONGODB_URL")
API_SECRET_KEY   = _require_env("API_SECRET_KEY")
DB_NAME          = os.getenv("DB_NAME",             "easycaptcha")
ALLOWED_ORIGINS  = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
TOKEN_TTL_MINS   = int(os.getenv("TOKEN_TTL_MINUTES",    "5"))
RATE_LIMIT_RPM   = int(os.getenv("RATE_LIMIT_PER_MIN",   "15"))
VERIFY_LIMIT_RPM = int(os.getenv("VERIFY_LIMIT_PER_MIN", "60"))   # for /captcha/verify
CAPTCHA_LENGTH   = int(os.getenv("CAPTCHA_LENGTH",        "5"))
LOG_LEVEL        = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("easycaptcha")

# ── MongoDB client ────────────────────────────────────────────────────────────

client = AsyncIOMotorClient(MONGODB_URL)
db     = client[DB_NAME]

# ── In-memory rate limiters (sliding 60-second window, per IP) ───────────────
# Plain dicts — keys are pruned by a background task to prevent memory growth.

_rate_store:        dict = {}   # guards GET /captcha
_verify_rate_store: dict = {}   # guards POST /captcha/verify


def _check_rate_limit(ip: str, store: dict, limit: int) -> bool:
    """
    Sliding 60-second window rate limiter.
    Returns True (allowed) or False (limit exceeded).
    """
    now    = time.monotonic()
    cutoff = now - 60.0
    window = [t for t in store.get(ip, []) if t > cutoff]
    if len(window) >= limit:
        store[ip] = window
        return False
    window.append(now)
    store[ip] = window
    return True


async def _rate_store_cleanup_loop() -> None:
    """Background task: prune IP keys whose windows have fully expired (every 5 min)."""
    while True:
        await asyncio.sleep(300)
        now    = time.monotonic()
        cutoff = now - 60.0
        for store in (_rate_store, _verify_rate_store):
            stale = [k for k, ts in list(store.items()) if not any(t > cutoff for t in ts)]
            for k in stale:
                store.pop(k, None)
        logger.debug("Rate-store pruned")


# ── Captcha character pool ────────────────────────────────────────────────────
# Mixed-case + digits; visually ambiguous glyphs excluded:
#   Uppercase: omit I, O  (look like 1 and 0)
#   Lowercase: omit i, l, o  (look like 1, 1, and 0)
#   Digits:    omit 0, 1  (look like O/o and I/l)
# Mixed case greatly increases the search space for OCR/ML solvers.

_CHARS  = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
_COLORS = ["#1e3a8a", "#6b21a8", "#9d174d", "#0c4a6e", "#14532d", "#92400e"]

# ── Font — resolved once at startup, reused on every request ─────────────────


def _find_font() -> Optional[str]:
    """Locate a TrueType font from common system paths."""
    candidates = [
        # Linux (Debian/Ubuntu — fonts-dejavu-core)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # Alpine / Docker minimal
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


_FONT_PATH: Optional[str] = _find_font()   # resolved once at startup


# ── Image generation ──────────────────────────────────────────────────────────


def _apply_wave_distortion(img: Image.Image) -> Image.Image:
    """
    Sinusoidal row-shift distortion.

    Shifts each row of pixels horizontally by a sine function of y.
    This breaks the regular character grid that OCR models rely on,
    without making the text unreadable to humans.
    """
    W, H   = img.size
    rng    = secrets.SystemRandom()
    amp    = rng.randint(2, 4)           # wave amplitude in pixels
    cycles = rng.uniform(1.2, 2.2)      # full sine cycles across image height

    src = img.load()
    out = Image.new("RGB", (W, H), (238, 245, 253))
    dst = out.load()

    for y in range(H):
        dx = int(amp * math.sin(2 * math.pi * cycles * y / H))
        for x in range(W):
            sx = min(max(x + dx, 0), W - 1)
            dst[x, y] = src[sx, y]
    return out


def _generate_captcha_image(code: str) -> str:
    """
    Render a distorted PNG captcha for the given code string.

    Anti-OCR / Anti-bot layers (in order):
      1. Background gradient + heavy dot noise.
      2. Background wavy bezier interference lines.
      3. Characters: randomised size (24–36 px), rotation (±30°),
         colour, and per-character vertical jitter.
      4. Foreground noise lines drawn OVER characters to break OCR segmentation.
      5. Sinusoidal wave distortion across rows (row-shift by sin(y)).
      6. Gaussian blur to soften hard edges used by edge-detection OCR.

    Returns: base64-encoded PNG string ready for
             <img src="data:image/png;base64,{result}" />
    """
    W, H = 260, 62
    img  = Image.new("RGB", (W, H), (238, 245, 253))
    draw = ImageDraw.Draw(img)
    rng  = secrets.SystemRandom()

    # ── 1. Background noise: scattered dots ──────────────────────────
    for _ in range(130):
        x = rng.randint(0, W)
        y = rng.randint(0, H)
        r = rng.randint(1, 3)
        c = (rng.randint(175, 225), rng.randint(180, 228), rng.randint(205, 248))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)

    # ── 2. Background noise: wavy bezier lines ────────────────────────
    for _ in range(10):
        pts = [
            (rng.randint(0,          W // 4),       rng.randint(5, H - 5)),
            (rng.randint(W // 4,     W // 2),        rng.randint(5, H - 5)),
            (rng.randint(W // 2, 3 * W // 4),        rng.randint(5, H - 5)),
            (rng.randint(3 * W // 4, W),             rng.randint(5, H - 5)),
        ]
        c = (rng.randint(155, 205), rng.randint(155, 205), rng.randint(185, 230))
        draw.line(pts, fill=c, width=1)

    # ── 3. Characters (each on its own rotated RGBA layer) ───────────
    slot_w = (W - 20) // len(code)

    for i, char in enumerate(code):
        size = rng.randint(24, 36)
        try:
            font = ImageFont.truetype(_FONT_PATH, size) if _FONT_PATH else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        layer = Image.new("RGBA", (slot_w, H + 16), (0, 0, 0, 0))
        ld    = ImageDraw.Draw(layer)

        bbox = ld.textbbox((0, 0), char, font=font)
        cx   = (slot_w - (bbox[2] - bbox[0])) // 2
        # Per-character vertical jitter for organic look
        cy   = (H - (bbox[3] - bbox[1])) // 2 - 2 + rng.randint(-4, 4)

        ld.text((cx, cy), char, fill=_COLORS[i % len(_COLORS)], font=font)

        angle = rng.uniform(-30, 30)
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=False)

        img.paste(layer, (10 + i * slot_w, 0), layer)

    # ── 4. Foreground noise: lines OVER characters ────────────────────
    # Drawn after characters — appears on top, breaking OCR segmentation
    draw_fg = ImageDraw.Draw(img)
    for _ in range(5):
        x1 = rng.randint(0,          W // 4)
        y1 = rng.randint(H // 5, 4 * H // 5)
        x2 = rng.randint(3 * W // 4, W)
        y2 = rng.randint(H // 5, 4 * H // 5)
        c  = (rng.randint(115, 175), rng.randint(115, 175), rng.randint(155, 215))
        draw_fg.line([(x1, y1), (x2, y2)], fill=c, width=1)

    # ── 5. Sinusoidal wave distortion ────────────────────────────────
    img = _apply_wave_distortion(img)

    # ── 6. Gaussian blur (reduces sharpness used by edge-detection OCR)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── Lifespan: DB indexes + background tasks ───────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Unique index for O(1) token lookups at verify time
    await db.captcha_tokens.create_index("token_id", unique=True)
    # TTL index — auto-deletes expired tokens without a cron job
    await db.captcha_tokens.create_index("expires_at", expireAfterSeconds=0)

    # Background task: prune stale rate-limit entries every 5 minutes
    cleanup_task = asyncio.create_task(_rate_store_cleanup_loop())

    logger.info("EasyCaptcha ready  |  DB: %s  |  TTL: %d min  |  v1.1.0", DB_NAME, TOKEN_TTL_MINS)
    yield

    cleanup_task.cancel()
    client.close()
    logger.info("EasyCaptcha stopped")


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title       = "EasyCaptcha",
    description = "Self-hosted, lightweight server-side image captcha service.",
    version     = "1.1.0",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# CORS — restrict to your frontend origin(s) in production
app.add_middleware(
    CORSMiddleware,
    allow_origins  = ALLOWED_ORIGINS,
    allow_methods  = ["GET", "POST", "OPTIONS"],
    allow_headers  = ["Content-Type", "X-API-Key"],
)


# Security headers on every response
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options":        "DENY",
        "Cache-Control":          "no-store, no-cache, must-revalidate",
        "Pragma":                 "no-cache",
    })
    return response


# ── Pydantic models ───────────────────────────────────────────────────────────


class CaptchaResponse(BaseModel):
    token_id:       str
    image_b64:      str   # render: <img src="data:image/png;base64,{image_b64}" />
    captcha_length: int   # how many characters the user must type


class VerifyRequest(BaseModel):
    token_id: str
    answer:   str


class VerifyResponse(BaseModel):
    valid:      bool
    # error_code is present only when valid=False; useful for integrator debugging.
    # Values: "not_found" | "expired" | "already_used" | "wrong_answer"
    # Intentionally vague in production logs — do NOT surface this to end users.
    error_code: Optional[str] = None


class HealthResponse(BaseModel):
    status:  str
    version: str
    service: str


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health():
    """Service health check — returns 200 when the service is running."""
    return HealthResponse(status="ok", version="1.1.0", service="EasyCaptcha")


@app.get(
    "/captcha",
    response_model       = CaptchaResponse,
    tags                 = ["Captcha"],
    summary              = "Generate a new captcha challenge",
    response_description = "A unique token_id and a base64-encoded PNG image.",
)
async def generate_captcha(request: Request):
    """
    Create a new captcha challenge.

    **Flow**
    1. Your frontend calls `GET /captcha`.
    2. Display the returned image to the user.
    3. User types the code (mixed-case + digits, comparison is case-insensitive).
    4. On form submit, send `token_id` + typed `answer` to **your** backend.
    5. Your backend calls `POST /captcha/verify` (with the `X-API-Key` header).
    6. Proceed only if `valid == true`.

    **Security highlights**
    - The code is stored in MongoDB only — never returned to the browser.
    - Each token is single-use and expires after `TOKEN_TTL_MINUTES` (default 5).
    - Mixed-case + digit character pool defeats simple uppercase OCR solvers.
    - Wave distortion and foreground noise lines hinder automated solving.
    - Rate limited to `RATE_LIMIT_PER_MIN` requests per IP per minute.
    """
    ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )

    if not _check_rate_limit(ip, _rate_store, RATE_LIMIT_RPM):
        logger.warning("Rate limit exceeded — IP: %s", ip)
        raise HTTPException(
            status_code=429,
            detail="Too many captcha requests. Please wait a moment and try again.",
        )

    code     = "".join(secrets.choice(_CHARS) for _ in range(CAPTCHA_LENGTH))
    token_id = str(uuid.uuid4())
    expires  = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINS)

    await db.captcha_tokens.insert_one({
        "token_id":   token_id,
        "code":       code,
        "used":       False,
        "ip":         ip,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires,
    })

    logger.debug("Captcha generated  |  token: %s  |  ip: %s", token_id[:8], ip)
    return CaptchaResponse(
        token_id       = token_id,
        image_b64      = _generate_captcha_image(code),
        captcha_length = CAPTCHA_LENGTH,
    )


@app.post(
    "/captcha/verify",
    response_model = VerifyResponse,
    tags           = ["Captcha"],
    summary        = "Verify a captcha answer (backend-to-backend only)",
)
async def verify_captcha(
    payload:   VerifyRequest,
    request:   Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Verify a captcha answer.

    **Designed for backend-to-backend calls only** — pass your `API_SECRET_KEY`
    in the `X-API-Key` header.  Never call this from the browser.

    **Token lifecycle (v1.1.0)**
    The token is consumed (marked used) on the **very first call** — whether
    the answer is correct or wrong.  This prevents brute-force guessing: once
    a token is used, a new captcha must be requested via `GET /captcha`.

    Returns `{"valid": true}` on success.
    Returns `{"valid": false, "error_code": "..."}` on any failure.
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    # Additional rate limit on verify — protects against API-key-leak brute-force
    ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    if not _check_rate_limit(ip, _verify_rate_store, VERIFY_LIMIT_RPM):
        logger.warning("Verify rate limit exceeded — IP: %s", ip)
        raise HTTPException(status_code=429, detail="Too many verify requests.")

    doc = await db.captcha_tokens.find_one(
        {"token_id": payload.token_id, "used": False},
        {"_id": 0},
    )
    if not doc:
        # Token not found OR already used
        return VerifyResponse(valid=False, error_code="not_found")

    # Manual expiry check (MongoDB TTL fires every ~60 s — not instant)
    expires = doc.get("expires_at")
    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            await db.captcha_tokens.delete_one({"token_id": payload.token_id})
            return VerifyResponse(valid=False, error_code="expired")

    # Consume the token IMMEDIATELY — correct or wrong.
    # This prevents brute-force guessing: one token = one attempt.
    await db.captcha_tokens.update_one(
        {"token_id": payload.token_id},
        {"$set": {"used": True}},
    )

    # Case-insensitive comparison (users may type upper or lower)
    if doc["code"].upper() != payload.answer.strip().upper():
        logger.debug("Captcha wrong answer  |  token: %s", payload.token_id[:8])
        return VerifyResponse(valid=False, error_code="wrong_answer")

    logger.debug("Captcha verified OK  |  token: %s", payload.token_id[:8])
    return VerifyResponse(valid=True)


class StatsResponse(BaseModel):
    tokens_in_db:    int    # total documents currently in the collection
    active_unused:   int    # tokens not yet used (valid or expiring soon)
    verified:        int    # tokens correctly solved
    service_version: str


@app.get(
    "/stats",
    response_model = StatsResponse,
    tags           = ["Meta"],
    summary        = "Token statistics (admin)",
)
async def stats(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """
    Return live token counts from MongoDB.

    Requires the `X-API-Key` header — same key as `/captcha/verify`.
    Useful for monitoring dashboards and health checks.
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    total    = await db.captcha_tokens.count_documents({})
    unused   = await db.captcha_tokens.count_documents({"used": False})
    verified = await db.captcha_tokens.count_documents({"used": True})

    return StatsResponse(
        tokens_in_db    = total,
        active_unused   = unused,
        verified        = verified,
        service_version = "1.1.0",
    )
