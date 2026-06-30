from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EmailCodeRequest(BaseModel):
    email: str
    captcha_token: str | None = None


class EmailCodeResponse(BaseModel):
    message: str
    cooldown_seconds: int
    debug_code: str | None = None


class EmailCodeVerifyRequest(BaseModel):
    email: str
    code: str = Field(..., min_length=4, max_length=12)


class AuthUserRead(BaseModel):
    id: int
    email: str | None
    display_name: str | None
    avatar_url: str | None
    role: str

    model_config = {"from_attributes": True}


class AuthLoginResponse(BaseModel):
    user: AuthUserRead


class AuthMessage(BaseModel):
    message: str


class AuthSessionRead(BaseModel):
    session_id: str
    user_id: int
    expires_at: datetime

    model_config = {"from_attributes": True}
