"""
LEGACY v1 — GET /auth/captcha endpoint that generated image captcha.
Replaced by POST /auth/captcha-session + Cloudflare Turnstile (v2). Archive only.
"""

# ── Captcha ───────────────────────────────────────────────────

@router.get("/auth/captcha", tags=["Auth"])
async def get_captcha():
    """
    Generate a server-side captcha challenge.

    Output: {token_id: str, image_b64: str}
    The code itself is stored in MongoDB ONLY — never returned to the client.
    Even direct API callers only receive a PNG image; they would need OCR to bypass it.
    Token expires after 5 minutes and is single-use.
    """
    CHARS    = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code     = "".join(_sec.choice(CHARS) for _ in range(5))
    token_id = str(uuid.uuid4())
    expires  = datetime.now(timezone.utc) + timedelta(minutes=5)

    await db.captcha_tokens.insert_one({
        "token_id":   token_id,
        "code":       code,
        "used":       False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires.isoformat(),
    })

    image_b64 = _generate_captcha_image(code)
    return {"token_id": token_id, "image_b64": image_b64}
