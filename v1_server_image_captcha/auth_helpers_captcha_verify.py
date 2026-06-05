"""
LEGACY v1 — Server-side image captcha verification helper.
Replaced by Cloudflare Turnstile (v2). Do NOT import — archive only.
"""

# ── Captcha helpers ───────────────────────────────────────────

async def _verify_captcha(token_id: str, answer: str) -> bool:
    """
    Server-side captcha verification — one-time use, 5-minute expiry enforced.

    Input:  token_id — UUID from /auth/captcha, answer — user-typed code
    Output: True if correct and not expired; False otherwise
    """
    doc = await db.captcha_tokens.find_one({"token_id": token_id, "used": False})
    if not doc:
        return False
    try:
        expires = datetime.fromisoformat(doc["expires_at"])
        if datetime.now(timezone.utc).replace(tzinfo=None) > expires.replace(tzinfo=None):
            await db.captcha_tokens.delete_one({"token_id": token_id})
            return False
    except Exception:
        return False
    if doc["code"].upper() != answer.strip().upper():
        return False
    # Mark as used immediately — prevents replay attacks
    await db.captcha_tokens.update_one({"token_id": token_id}, {"$set": {"used": True}})
    return True
