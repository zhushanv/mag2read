from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta

from backend.app.core.config import get_settings


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(normalize_email(email)))


def generate_email_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_email_code(email: str, code: str) -> str:
    settings = get_settings()
    payload = f"{normalize_email(email)}:{code}:{settings.auth_code_secret}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_session_id() -> str:
    return secrets.token_urlsafe(48)


def session_expires_at() -> datetime:
    settings = get_settings()
    return datetime.now() + timedelta(days=settings.auth_session_days)
