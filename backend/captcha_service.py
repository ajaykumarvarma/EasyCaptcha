"""
EasyCaptcha — Self-Hosted Image Captcha Service
================================================
Version : 1.0.0
License : MIT

A minimal, dependency-light FastAPI service that generates server-side
image captcha challenges and verifies answers.  No external CAPTCHA
vendors required.

Endpoints
---------
  GET  /captcha          — Generate a new challenge (token_id + base64 PNG)
  POST /captcha/verify   — Verify an answer from your backend (requires API key)
  GET  /health           — Health check

Quick start
-----------
  1. Copy .env.example → .env and fill in values.
  2. pip install -r requirements.txt
  3. uvicorn captcha_service:app --host 0.0.0.0 --port 8080 --reload
     OR: docker compose -f ../docker/docker-compose.yml up
"""

import base64
import io
import logging
import os
import secrets
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel

load_dotenv()

# ── Configuration (all from environment — no hardcoded values) ───────────────

MONGODB_URL       = os.environ["MONGODB_URL"]           # Required
DB_NAME           = os.getenv("DB_NAME",            "easycaptcha")
API_SECRET_KEY    = os.environ["API_SECRET_KEY"]        # Required — used by /captcha/verify
ALLOWED_ORIGINS   = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
TOKEN_TTL_MINS    = int(os.getenv("TOKEN_TTL_MINUTES",    "5"))    # Minutes until a token expires
RATE_LIMIT_RPM    = int(os.getenv("RATE_LIMIT_PER_MIN",  "15"))    # Max /captcha calls per IP/min
CAPTCHA_LENGTH    = int(os.getenv("CAPTCHA_LENGTH",       "5"))     # Characters in each challenge
LOG_LEVEL         = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("easycaptcha")

# ── MongoDB client ────────────────────────────────────────────────────────────

client = AsyncIOMotorClient(MONGODB_URL)
db     = client[DB_NAME]

# ── In-memory rate limiter (per IP, sliding window) ──────────────────────────

_rate_store: dict = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    """
    Return True if the IP is within the allowed rate limit, False if exceeded.
    Uses a sliding 60-second window stored in process memory.
    Note: resets on restart — use Redis if you need persistence across restarts.
    """
    now    = time.monotonic()
    cutoff = now - 60.0
    _rate_store[ip] = [t for t in _rate_store[ip] if t > cutoff]
    if len(_rate_store[ip]) >= RATE_LIMIT_RPM:
        return False
    _rate_store[ip].append(now)
    return True


# ── Captcha constants ─────────────────────────────────────────────────────────

# Omit I, O, 0, 1 to prevent visual ambiguity for users
_CHARS  = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_COLORS = ["#1e3a8a", "#6b21a8", "#9d174d", "#0c4a6e", "#14532d", "#92400e"]


# ── Image generation ──────────────────────────────────────────────────────────

def _find_font() -> Optional[str]:
    """Locate a bold TrueType font from common system paths."""
    candidates = [
        # Linux (Debian/Ubuntu — installed via fonts-dejavu-core)
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


def _generate_captcha_image(code: str) -> str:
    """
    Render a distorted PNG captcha for the given code string.

    Steps:
      1. Fill background with a light blue-grey gradient simulation.
      2. Scatter random noise dots and wavy lines to hinder OCR.
      3. Draw each character at a random size and rotation, each a different colour.
      4. Apply a soft Gaussian blur to further confuse pixel-level attacks.

    Returns: base64-encoded PNG string ready for <img src="data:image/png;base64,...">
    """
    W, H      = 260, 62
    img       = Image.new("RGB", (W, H), (238, 245, 253))
    draw      = ImageDraw.Draw(img)
    font_path = _find_font()

    # ── Background noise: scattered dots ─────────────────────────
    rng = secrets.SystemRandom()
    for _ in range(100):
        x = rng.randint(0, W)
        y = rng.randint(0, H)
        r = rng.randint(1, 3)
        c = (rng.randint(180, 225), rng.randint(185, 228), rng.randint(210, 248))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)

    # ── Background noise: wavy lines ─────────────────────────────
    for _ in range(7):
        pts = [
            (rng.randint(0, W // 4),         rng.randint(5, H - 5)),
            (rng.randint(W // 4, W // 2),     rng.randint(5, H - 5)),
            (rng.randint(W // 2, 3 * W // 4), rng.randint(5, H - 5)),
            (rng.randint(3 * W // 4, W),      rng.randint(5, H - 5)),
        ]
        c = (rng.randint(145, 200), rng.randint(145, 200), rng.randint(185, 230))
        draw.line(pts, fill=c, width=1)

    # ── Draw characters (each on its own rotated RGBA layer) ─────
    slot_w = (W - 20) // len(code)

    for i, char in enumerate(code):
        size = rng.randint(28, 38)
        try:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        # Transparent layer per character so rotation doesn't bleed
        layer = Image.new("RGBA", (slot_w, H + 16), (0, 0, 0, 0))
        ld    = ImageDraw.Draw(layer)

        bbox = ld.textbbox((0, 0), char, font=font)
        cx   = (slot_w - (bbox[2] - bbox[0])) // 2
        cy   = (H - (bbox[3] - bbox[1])) // 2 - 2

        ld.text((cx, cy), char, fill=_COLORS[i % len(_COLORS)], font=font)

        # Rotate ± up to 30 degrees
        angle = rng.uniform(-30, 30)
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=False)

        img.paste(layer, (10 + i * slot_w, 0), layer)

    # ── Final soft blur (anti-OCR) ────────────────────────────────
    img = img.filter(ImageFilter.GaussianBlur(radius=0.7))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── Lifespan: DB setup ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # MongoDB TTL index — auto-deletes expired tokens without a cron job
    await db.captcha_tokens.create_index("expires_at", expireAfterSeconds=0)
    logger.info("EasyCaptcha ready  |  DB: %s  |  TTL: %d min", DB_NAME, TOKEN_TTL_MINS)
    yield
    client.close()
    logger.info("EasyCaptcha stopped")


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title       = "EasyCaptcha",
    description = "Self-hosted, lightweight server-side image captcha service.",
    version     = "1.0.0",
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
    image_b64:      str          # render: <img src="data:image/png;base64,{image_b64}" />
    captcha_length: int          # number of characters the user must type; mirrors CAPTCHA_LENGTH


class VerifyRequest(BaseModel):
    token_id: str
    answer:   str


class VerifyResponse(BaseModel):
    valid: bool


class HealthResponse(BaseModel):
    status:  str
    version: str
    service: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health():
    """Service health check — returns 200 when the service is running."""
    return HealthResponse(status="ok", version="1.0.0", service="EasyCaptcha")


@app.get(
    "/captcha",
    response_model = CaptchaResponse,
    tags           = ["Captcha"],
    summary        = "Generate a new captcha challenge",
    response_description = "A unique token_id and a base64-encoded PNG image.",
)
async def generate_captcha(request: Request):
    """
    Create a new captcha challenge.

    **Flow**
    1. Your frontend calls `GET /captcha`.
    2. Display the returned image to the user.
    3. User types the code into an input field.
    4. On form submit, send `token_id` + typed `answer` to **your** backend.
    5. Your backend calls `POST /captcha/verify` (with the `X-API-Key` header).
    6. Proceed only if `valid == true`.

    **Security**
    - The code is stored in MongoDB only — it is never returned to the client.
    - Each token is single-use and expires after `TOKEN_TTL_MINUTES` (default 5).
    - Rate limited to `RATE_LIMIT_PER_MIN` requests per IP per minute.
    """
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() \
         or (request.client.host if request.client else "unknown")

    if not _check_rate_limit(ip):
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
        "expires_at": expires,          # datetime object — required for MongoDB TTL index
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
    summary        = "Verify a captcha answer (backend-to-backend)",
)
async def verify_captcha(
    payload:   VerifyRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Verify a captcha answer.

    **This endpoint is designed to be called by your backend, not directly
    by a browser.**  Pass your `API_SECRET_KEY` in the `X-API-Key` header.

    Returns `{"valid": true}` on success, `{"valid": false}` on any failure
    (wrong answer, expired token, already used, or missing token).

    A token is marked *used* immediately upon the first correct verification
    to prevent replay attacks.
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    doc = await db.captcha_tokens.find_one(
        {"token_id": payload.token_id, "used": False},
        {"_id": 0},
    )
    if not doc:
        return VerifyResponse(valid=False)

    # Manual expiry check (MongoDB TTL fires every ~60 s — not instant)
    expires = doc.get("expires_at")
    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            await db.captcha_tokens.delete_one({"token_id": payload.token_id})
            return VerifyResponse(valid=False)

    # Case-insensitive comparison
    if doc["code"].upper() != payload.answer.strip().upper():
        logger.debug("Captcha wrong answer  |  token: %s", payload.token_id[:8])
        return VerifyResponse(valid=False)

    # Mark as used — prevents replay
    await db.captcha_tokens.update_one(
        {"token_id": payload.token_id},
        {"$set": {"used": True}},
    )
    logger.debug("Captcha verified OK  |  token: %s", payload.token_id[:8])
    return VerifyResponse(valid=True)


class StatsResponse(BaseModel):
    tokens_in_db:    int    # total documents currently in the collection
    active_unused:   int    # tokens not yet used (may still be valid or expiring soon)
    verified:        int    # tokens that were correctly solved and marked used
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

    Requires the `X-API-Key` header — same key as used for `/captcha/verify`.
    Useful for monitoring dashboards and health checks.

    Fields
    ------
    - `tokens_in_db`  — total documents currently in the collection (MongoDB TTL
                        auto-deletes expired ones every ~60 s, so this reflects recent activity).
    - `active_unused` — tokens that have not been solved yet (valid or about to expire).
    - `verified`      — tokens correctly solved by a real user.
    - `service_version` — current service version string.
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
        service_version = "1.0.0",
    )
