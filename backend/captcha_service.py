"""
EasyCaptcha — Self-Hosted Image Captcha Service
================================================
Version : 1.2.0
License : MIT

Endpoints
---------
  GET  /captcha                   — Generate a new challenge
  GET  /captcha/audio/{token_id}  — Audio pronunciation (WCAG 2.1 accessibility)
  POST /captcha/verify            — Verify an answer (backend-to-backend, API key required)
  GET  /stats                     — Token statistics (API key required)
  GET  /health                    — Health check

Changes in 1.2.0
----------------
  - MongoDB authentication in docker-compose (dedicated captcha_svc user, least privilege).
  - IP binding: token is tied to the IP that requested it; optional ENFORCE_IP_BINDING config.
  - Audio CAPTCHA endpoint: GET /captcha/audio/{token_id} returns WAV via espeak-ng.
    Allows visually impaired users to hear the challenge (WCAG 2.1 SC 1.1.1).
  - VerifyRequest.client_ip: optional field so integrators can pass the end-user IP.
"""

import asyncio
import base64
import io
import logging
import math
import os
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(
            f"FATAL: '{key}' env var not set. "
            "Copy backend/.env.example → backend/.env and fill in the required values."
        )
    return val


MONGODB_URL       = _require_env("MONGODB_URL")
API_SECRET_KEY    = _require_env("API_SECRET_KEY")
DB_NAME           = os.getenv("DB_NAME",             "easycaptcha")
ALLOWED_ORIGINS   = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
TOKEN_TTL_MINS    = int(os.getenv("TOKEN_TTL_MINUTES",    "5"))
RATE_LIMIT_RPM    = int(os.getenv("RATE_LIMIT_PER_MIN",   "15"))
VERIFY_LIMIT_RPM  = int(os.getenv("VERIFY_LIMIT_PER_MIN", "60"))
AUDIO_LIMIT_RPM   = int(os.getenv("AUDIO_LIMIT_PER_MIN",  "20"))
CAPTCHA_LENGTH    = int(os.getenv("CAPTCHA_LENGTH",        "5"))
ENFORCE_IP_BINDING = os.getenv("ENFORCE_IP_BINDING", "false").strip().lower() == "true"
CAPTCHA_MIN_SOLVE_MS = int(os.getenv("CAPTCHA_MIN_SOLVE_MS", "1500"))  # 0 = disabled
LOG_LEVEL         = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("easycaptcha")

# ── MongoDB client ────────────────────────────────────────────────────────────

client = AsyncIOMotorClient(MONGODB_URL)
db     = client[DB_NAME]

# ── In-memory rate limiters (sliding 60-second window, per IP) ───────────────

_rate_store:        dict = {}   # GET /captcha
_verify_rate_store: dict = {}   # POST /captcha/verify
_audio_rate_store:  dict = {}   # GET /captcha/audio/{id}


def _check_rate_limit(ip: str, store: dict, limit: int) -> bool:
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
    """Prune fully-expired IP entries every 5 minutes to prevent memory growth."""
    while True:
        await asyncio.sleep(300)
        now    = time.monotonic()
        cutoff = now - 60.0
        for store in (_rate_store, _verify_rate_store, _audio_rate_store):
            stale = [k for k, ts in list(store.items()) if not any(t > cutoff for t in ts)]
            for k in stale:
                store.pop(k, None)
        logger.debug("Rate-store pruned")


# ── Captcha character pool ────────────────────────────────────────────────────
# Mixed-case + digits; visually ambiguous glyphs excluded:
#   Uppercase: omit I, O
#   Lowercase: omit i, l, o
#   Digits:    omit 0, 1

_CHARS  = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
_COLORS = ["#1e3a8a", "#6b21a8", "#9d174d", "#0c4a6e", "#14532d", "#92400e"]

# ── Font — resolved once at startup ──────────────────────────────────────────


def _find_font() -> Optional[str]:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


_FONT_PATH: Optional[str] = _find_font()


# ── Image generation ──────────────────────────────────────────────────────────


def _apply_wave_distortion(img: Image.Image) -> Image.Image:
    W, H   = img.size
    rng    = secrets.SystemRandom()
    amp    = rng.randint(2, 4)
    cycles = rng.uniform(1.2, 2.2)
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
    W, H = 260, 62
    img  = Image.new("RGB", (W, H), (238, 245, 253))
    draw = ImageDraw.Draw(img)
    rng  = secrets.SystemRandom()

    # Background noise dots (increased for stronger OCR resistance)
    for _ in range(180):
        x = rng.randint(0, W); y = rng.randint(0, H); r = rng.randint(1, 3)
        c = (rng.randint(175, 225), rng.randint(180, 228), rng.randint(205, 248))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)

    # Background interference lines
    for _ in range(12):
        pts = [
            (rng.randint(0, W // 4), rng.randint(5, H - 5)),
            (rng.randint(W // 4, W // 2), rng.randint(5, H - 5)),
            (rng.randint(W // 2, 3 * W // 4), rng.randint(5, H - 5)),
            (rng.randint(3 * W // 4, W), rng.randint(5, H - 5)),
        ]
        c = (rng.randint(155, 205), rng.randint(155, 205), rng.randint(185, 230))
        draw.line(pts, fill=c, width=1)

    # Variable character spacing — harder for segmentation-based OCR
    slot_w = (W - 20) // len(code)
    offsets = [rng.randint(-3, 3) for _ in range(len(code))]
    for i, char in enumerate(code):
        size = rng.randint(24, 36)
        try:
            font = ImageFont.truetype(_FONT_PATH, size) if _FONT_PATH else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        layer = Image.new("RGBA", (slot_w, H + 16), (0, 0, 0, 0))
        ld    = ImageDraw.Draw(layer)
        bbox  = ld.textbbox((0, 0), char, font=font)
        cx    = (slot_w - (bbox[2] - bbox[0])) // 2 + offsets[i]
        cy    = (H - (bbox[3] - bbox[1])) // 2 - 2 + rng.randint(-5, 5)
        ld.text((cx, cy), char, fill=_COLORS[i % len(_COLORS)], font=font)
        layer = layer.rotate(rng.uniform(-33, 33), resample=Image.BICUBIC, expand=False)
        img.paste(layer, (10 + i * slot_w, 0), layer)

    draw_fg = ImageDraw.Draw(img)
    # Foreground lines crossing characters
    for _ in range(8):
        x1 = rng.randint(0, W // 4); y1 = rng.randint(H // 5, 4 * H // 5)
        x2 = rng.randint(3 * W // 4, W); y2 = rng.randint(H // 5, 4 * H // 5)
        c  = (rng.randint(115, 175), rng.randint(115, 175), rng.randint(155, 215))
        draw_fg.line([(x1, y1), (x2, y2)], fill=c, width=1)

    # Arc noise over characters (makes segmentation harder)
    for _ in range(3):
        x0 = rng.randint(W // 5, 4 * W // 5)
        y0 = rng.randint(-10, H + 10)
        r  = rng.randint(18, 35)
        c  = (rng.randint(120, 180), rng.randint(120, 180), rng.randint(160, 220))
        draw_fg.arc([x0 - r, y0 - r, x0 + r, y0 + r], start=rng.randint(0, 180),
                    end=rng.randint(181, 360), fill=c, width=1)

    img = _apply_wave_distortion(img)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── Audio captcha (WCAG 2.1 accessibility) ───────────────────────────────────


def _espeak_available() -> bool:
    """Return True if espeak-ng is installed on the system."""
    return shutil.which("espeak-ng") is not None


def _generate_audio_captcha(code: str) -> bytes:
    """
    Generate a WAV audio file that spells out each captcha character individually.

    Uses espeak-ng for high-quality, offline, privacy-preserving speech synthesis.
    Install: apt install espeak-ng  (included in the Docker image by default).

    Raises FileNotFoundError if espeak-ng is not installed.
    """
    if not _espeak_available():
        raise FileNotFoundError(
            "espeak-ng is not installed. "
            "Run: apt install espeak-ng  (or add it to your Dockerfile)."
        )

    # Double-space between characters gives espeak-ng a clear pause
    spelled = "  ".join(code)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
    try:
        subprocess.run(
            [
                "espeak-ng",
                "-w", tmp_path,   # write WAV output to file
                "-s", "95",       # speed: 95 words/min (slow + clear)
                "-a", "180",      # amplitude/volume (0–200)
                "-g", "25",       # gap between words (centiseconds)
                spelled,
            ],
            check=True,
            timeout=15,
            capture_output=True,
        )
        with open(tmp_path, "rb") as f:
            return f.read()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("espeak-ng process failed") from exc
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.captcha_tokens.create_index("token_id", unique=True)
    await db.captcha_tokens.create_index("expires_at", expireAfterSeconds=0)

    cleanup_task = asyncio.create_task(_rate_store_cleanup_loop())

    audio_status = "available" if _espeak_available() else "unavailable (install espeak-ng)"
    logger.info(
        "EasyCaptcha ready  |  DB: %s  |  TTL: %d min  |  IP binding: %s  |  audio: %s  |  min_solve: %dms  |  v1.3.0",
        DB_NAME, TOKEN_TTL_MINS, ENFORCE_IP_BINDING, audio_status, CAPTCHA_MIN_SOLVE_MS,
    )
    yield

    cleanup_task.cancel()
    client.close()
    logger.info("EasyCaptcha stopped")


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title       = "EasyCaptcha",
    description = "Self-hosted, lightweight server-side image captcha service.",
    version     = "1.3.0",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ALLOWED_ORIGINS,
    allow_methods  = ["GET", "POST", "OPTIONS"],
    allow_headers  = ["Content-Type", "X-API-Key"],
)


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
    token_id:        str
    image_b64:       str
    captcha_length:  int
    audio_available: bool   # true if espeak-ng is installed — show audio button in UI


class VerifyRequest(BaseModel):
    token_id:  str
    answer:    str
    # Optional: end-user's IP forwarded by your backend.
    # Required only when ENFORCE_IP_BINDING=true.
    # Example (Express): client_ip: req.ip
    # Example (Django):  client_ip: request.META.get('REMOTE_ADDR')
    client_ip: Optional[str] = None


class VerifyResponse(BaseModel):
    valid:      bool
    # error_code: debugging only — do NOT surface this message to end users.
    # Values: not_found | expired | wrong_answer | ip_missing | ip_mismatch | too_fast
    error_code: Optional[str] = None


class HealthResponse(BaseModel):
    status:          str
    version:         str
    service:         str
    audio_available: bool


# ── Routes ────────────────────────────────────────────────────────────────────


def _get_ip(request: Request) -> str:
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health():
    return HealthResponse(
        status          = "ok",
        version         = "1.3.0",
        service         = "EasyCaptcha",
        audio_available = _espeak_available(),
    )


@app.get(
    "/captcha",
    response_model = CaptchaResponse,
    tags           = ["Captcha"],
    summary        = "Generate a new captcha challenge",
)
async def generate_captcha(request: Request):
    """
    Create a new captcha challenge.

    **Flow**
    1. Frontend calls `GET /captcha`.
    2. Display the image (and optionally the audio button) to the user.
    3. User types the characters (or listens via `GET /captcha/audio/{token_id}`).
    4. On form submit, send `token_id` + `answer` to **your** backend.
    5. Your backend calls `POST /captcha/verify` with the `X-API-Key` header.
    6. If `valid == true`, proceed. Otherwise refresh the captcha.

    **IP Binding (optional)**
    When `ENFORCE_IP_BINDING=true`, also pass `client_ip` in the verify request.
    The service checks that the verifying IP matches the generating IP,
    preventing token-theft attacks where a captured token_id is used from
    a different machine.
    """
    ip = _get_ip(request)

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
        token_id        = token_id,
        image_b64       = _generate_captcha_image(code),
        captcha_length  = CAPTCHA_LENGTH,
        audio_available = _espeak_available(),
    )


@app.get(
    "/captcha/audio/{token_id}",
    tags    = ["Captcha"],
    summary = "Audio pronunciation for accessibility (WCAG 2.1)",
)
async def captcha_audio(token_id: str, request: Request):
    """
    Return a WAV audio file that pronounces the captcha characters.

    **Designed for visually impaired users / screen reader users.**
    The audio spells out each character of the challenge individually
    with clear pauses between them.

    - Does NOT consume the token — user still needs to type and verify.
    - Rate limited to `AUDIO_LIMIT_PER_MIN` (default 20) per IP per minute.
    - Requires espeak-ng to be installed (included in the Docker image).
    - Returns 503 if espeak-ng is not available.

    **Note:** Audio captchas are inherently less resistant to automated solving
    than image captchas. Use `ServerCaptcha` (server-side) for high-risk flows;
    audio is an accessibility supplement, not the primary challenge.
    """
    ip = _get_ip(request)

    if not _check_rate_limit(ip, _audio_rate_store, AUDIO_LIMIT_RPM):
        raise HTTPException(status_code=429, detail="Too many audio requests.")

    doc = await db.captcha_tokens.find_one(
        {"token_id": token_id, "used": False},
        {"_id": 0, "code": 1, "expires_at": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Captcha not found or already used.")

    expires = doc.get("expires_at")
    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            await db.captcha_tokens.delete_one({"token_id": token_id})
            raise HTTPException(status_code=410, detail="Captcha has expired.")

    try:
        # Run blocking subprocess in a thread pool — don't block the event loop
        audio_bytes = await asyncio.get_event_loop().run_in_executor(
            None, _generate_audio_captcha, doc["code"]
        )
    except FileNotFoundError as exc:
        logger.warning("Audio requested but espeak-ng not installed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Audio captcha is not available on this server. "
                "Install espeak-ng (apt install espeak-ng) and restart the service."
            ),
        )
    except Exception as exc:
        logger.error("Audio generation error: %s", exc)
        raise HTTPException(status_code=500, detail="Audio generation failed.")

    logger.debug("Audio served  |  token: %s  |  ip: %s", token_id[:8], ip)
    return Response(
        content     = audio_bytes,
        media_type  = "audio/wav",
        headers     = {
            "Content-Disposition": 'inline; filename="captcha.wav"',
            "Cache-Control":       "no-store, no-cache",
            "Pragma":              "no-cache",
        },
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

    **Backend-to-backend only** — requires the `X-API-Key` header.

    **Token lifecycle**
    The token is consumed on the first verify call (correct OR wrong).
    One token = one attempt.  Refresh via `GET /captcha` after any failure.

    **IP Binding** (when `ENFORCE_IP_BINDING=true`)
    Pass `client_ip` in the request body (the end-user's IP address, as seen by
    your backend).  The service rejects the request if it doesn't match the IP
    that originally called `GET /captcha`.
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    ip = _get_ip(request)
    if not _check_rate_limit(ip, _verify_rate_store, VERIFY_LIMIT_RPM):
        raise HTTPException(status_code=429, detail="Too many verify requests.")

    doc = await db.captcha_tokens.find_one(
        {"token_id": payload.token_id, "used": False},
        {"_id": 0},
    )
    if not doc:
        return VerifyResponse(valid=False, error_code="not_found")

    expires = doc.get("expires_at")
    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            await db.captcha_tokens.delete_one({"token_id": payload.token_id})
            return VerifyResponse(valid=False, error_code="expired")

    # ── IP binding check ──────────────────────────────────────────────
    if ENFORCE_IP_BINDING:
        stored_ip   = doc.get("ip", "unknown")
        provided_ip = (payload.client_ip or "").strip()
        if not provided_ip:
            logger.warning(
                "IP binding: client_ip missing  |  token: %s", payload.token_id[:8]
            )
            # Consume token to prevent future guesses
            await db.captcha_tokens.update_one(
                {"token_id": payload.token_id}, {"$set": {"used": True}}
            )
            return VerifyResponse(valid=False, error_code="ip_missing")

        if provided_ip != stored_ip:
            logger.warning(
                "IP binding mismatch  |  token: %s  |  stored: %s  |  provided: %s",
                payload.token_id[:8], stored_ip, provided_ip,
            )
            await db.captcha_tokens.update_one(
                {"token_id": payload.token_id}, {"$set": {"used": True}}
            )
            return VerifyResponse(valid=False, error_code="ip_mismatch")

    # ── Consume token (one attempt only) ─────────────────────────────
    await db.captcha_tokens.update_one(
        {"token_id": payload.token_id},
        {"$set": {"used": True}},
    )

    # ── Minimum solve time (anti-bot timing check) ───────────────────
    # Real humans take ≥1.5 s to read and type; automated solvers answer in <50 ms.
    if CAPTCHA_MIN_SOLVE_MS > 0:
        created = doc.get("created_at")
        if created:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            elapsed_ms = (datetime.now(timezone.utc) - created).total_seconds() * 1000
            if elapsed_ms < CAPTCHA_MIN_SOLVE_MS:
                logger.warning(
                    "Bot suspected — solve too fast  |  token: %s  |  %.0f ms < %d ms",
                    payload.token_id[:8], elapsed_ms, CAPTCHA_MIN_SOLVE_MS,
                )
                return VerifyResponse(valid=False, error_code="too_fast")

    # ── Answer check (strict case — must match exactly as displayed) ────────
    if doc["code"] != payload.answer.strip():
        logger.debug("Wrong answer  |  token: %s", payload.token_id[:8])
        return VerifyResponse(valid=False, error_code="wrong_answer")

    logger.debug("Verified OK   |  token: %s", payload.token_id[:8])
    return VerifyResponse(valid=True)


class StatsResponse(BaseModel):
    tokens_in_db:    int
    active_unused:   int
    verified:        int
    service_version: str


@app.get("/stats", response_model=StatsResponse, tags=["Meta"])
async def stats(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if not x_api_key or not secrets.compare_digest(x_api_key, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    total    = await db.captcha_tokens.count_documents({})
    unused   = await db.captcha_tokens.count_documents({"used": False})
    verified = await db.captcha_tokens.count_documents({"used": True})

    return StatsResponse(
        tokens_in_db    = total,
        active_unused   = unused,
        verified        = verified,
        service_version = "1.3.0",
    )
