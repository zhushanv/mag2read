from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import (
    generate_email_code,
    generate_session_id,
    hash_email_code,
    is_valid_email,
    normalize_email,
    session_expires_at,
)
from backend.app.models.task import AuthAuditLog, EmailVerificationCode, User, UserSession
from backend.app.services import email_service


class AuthError(ValueError):
    pass


def client_ip(request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def user_agent(request) -> str | None:
    value = request.headers.get("user-agent")
    return value[:500] if value else None


def write_audit_log(
    db: Session,
    *,
    action: str,
    success: bool,
    user_id: int | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    user_agent_value: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        AuthAuditLog(
            user_id=user_id,
            email=normalize_email(email) if email else None,
            action=action,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent_value,
            detail=detail[:500] if detail else None,
        )
    )
    db.commit()


def ensure_can_send_code(db: Session, email: str) -> None:
    settings = get_settings()
    email = normalize_email(email)
    now = datetime.now()
    latest = db.execute(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.email == email)
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest and latest.created_at and (now - latest.created_at).total_seconds() < settings.auth_code_send_interval_seconds:
        raise AuthError("验证码发送过于频繁，请稍后再试")

    window_start = now - timedelta(minutes=10)
    recent_count = len(
        db.execute(
            select(EmailVerificationCode.id).where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.created_at >= window_start,
            )
        ).all()
    )
    if recent_count >= 5:
        raise AuthError("验证码请求次数过多，请稍后再试")


def request_email_code(db: Session, email: str, *, ip_address: str | None, user_agent_value: str | None) -> str:
    settings = get_settings()
    email = normalize_email(email)
    if not is_valid_email(email):
        raise AuthError("请输入有效邮箱")
    ensure_can_send_code(db, email)

    code = generate_email_code()
    item = EmailVerificationCode(
        email=email,
        code_hash=hash_email_code(email, code),
        purpose="login",
        expires_at=datetime.now() + timedelta(minutes=settings.auth_code_ttl_minutes),
        send_ip=ip_address,
        user_agent=user_agent_value,
    )
    db.add(item)
    db.commit()
    email_service.send_login_code(email, code)
    write_audit_log(
        db,
        action="email_code_requested",
        success=True,
        email=email,
        ip_address=ip_address,
        user_agent_value=user_agent_value,
    )
    return code


def verify_captcha(token: str | None, *, ip_address: str | None) -> None:
    settings = get_settings()
    if not settings.auth_captcha_enabled:
        return
    if not settings.turnstile_secret_key:
        raise AuthError("人机验证服务未配置")
    if not token:
        raise AuthError("请完成人机验证")

    data = urllib.parse.urlencode(
        {
            "secret": settings.turnstile_secret_key,
            "response": token,
            "remoteip": ip_address or "",
        }
    ).encode("utf-8")
    request = urllib.request.Request("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise AuthError("人机验证服务暂时不可用") from exc
    if not payload.get("success"):
        raise AuthError("人机验证失败")


def get_or_create_user_by_email(db: Session, email: str) -> User:
    email = normalize_email(email)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is not None:
        return user

    username_base = email.split("@", 1)[0][:54] or "user"
    username = username_base
    suffix = 1
    while db.execute(select(User.id).where(User.username == username)).scalar_one_or_none() is not None:
        suffix += 1
        username = f"{username_base}_{suffix}"[:64]

    user = User(
        username=username,
        email=email,
        display_name=username_base,
        role="user",
        status="active",
        last_login_at=datetime.now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_session(db: Session, user: User, *, ip_address: str | None, user_agent_value: str | None) -> UserSession:
    session = UserSession(
        session_id=generate_session_id(),
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent_value,
        expires_at=session_expires_at(),
    )
    user.last_login_at = datetime.now()
    db.add(user)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def verify_email_code(
    db: Session,
    email: str,
    code: str,
    *,
    ip_address: str | None,
    user_agent_value: str | None,
) -> tuple[User, UserSession]:
    email = normalize_email(email)
    if not is_valid_email(email):
        raise AuthError("请输入有效邮箱")

    item = db.execute(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == "login",
            EmailVerificationCode.used_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if item is None or item.expires_at < datetime.now():
        write_audit_log(db, action="email_code_failed", success=False, email=email, ip_address=ip_address, user_agent_value=user_agent_value, detail="expired")
        raise AuthError("验证码不正确或已过期")
    if item.attempt_count >= 5:
        raise AuthError("验证码尝试次数过多，请重新获取")

    item.attempt_count += 1
    if item.code_hash != hash_email_code(email, code.strip()):
        db.add(item)
        db.commit()
        write_audit_log(db, action="email_code_failed", success=False, email=email, ip_address=ip_address, user_agent_value=user_agent_value, detail="mismatch")
        raise AuthError("验证码不正确或已过期")

    item.used_at = datetime.now()
    user = get_or_create_user_by_email(db, email)
    if user.status != "active":
        raise AuthError("账号已被禁用")
    session = create_session(db, user, ip_address=ip_address, user_agent_value=user_agent_value)
    db.add(item)
    db.commit()
    write_audit_log(db, action="email_code_verified", success=True, user_id=user.id, email=email, ip_address=ip_address, user_agent_value=user_agent_value)
    return user, session


def get_valid_session(db: Session, session_id: str | None) -> UserSession | None:
    if not session_id:
        return None
    session = db.execute(select(UserSession).where(UserSession.session_id == session_id)).scalar_one_or_none()
    if session is None or session.revoked_at is not None or session.expires_at < datetime.now():
        return None
    return session


def get_user(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def revoke_session(db: Session, session: UserSession) -> None:
    session.revoked_at = datetime.now()
    db.add(session)
    db.commit()
