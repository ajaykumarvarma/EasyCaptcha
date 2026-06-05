"""
LEGACY v1 — Request models with captcha_token_id + captcha_answer fields.
Replaced by cf_turnstile_token + cf_session_id fields (v2). Archive only.
"""

from pydantic import BaseModel

class SignUpReq(BaseModel):
    first_name:       str
    last_name:        str
    email:            str
    username:         str
    password:         str
    captcha_token_id: str
    captcha_answer:   str


class SignInReq(BaseModel):
    identifier:       str   # accepts email OR username
    password:         str
    captcha_token_id: str
    captcha_answer:   str


class ResetPasswordReq(BaseModel):
    token:        str
    new_password: str


class ResendVerificationReq(BaseModel):
    identifier: str


class ForgotPasswordReq(BaseModel):
    identifier:       str
    captcha_token_id: str
    captcha_answer:   str
