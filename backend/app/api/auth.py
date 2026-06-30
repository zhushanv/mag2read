from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from backend.app.core.auth_dependencies import get_current_user
from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.schemas.auth import AuthLoginResponse, AuthMessage, AuthUserRead, EmailCodeRequest, EmailCodeResponse, EmailCodeVerifyRequest
from backend.app.services import auth_service, email_service


router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_session_cookie(response: Response, session_id: str) -> None:
    settings = get_settings()
    secure = settings.app_env.lower() == "production"
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=session_id,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.auth_cookie_name, path="/")


@router.post("/email/request-code", response_model=EmailCodeResponse)
def request_email_code(payload: EmailCodeRequest, request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    ip_address = auth_service.client_ip(request)
    user_agent_value = auth_service.user_agent(request)
    try:
        auth_service.verify_captcha(payload.captcha_token, ip_address=ip_address)
        code = auth_service.request_email_code(
            db,
            payload.email,
            ip_address=ip_address,
            user_agent_value=user_agent_value,
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    debug_code = code if settings.debug and not email_service.smtp_configured() else None
    return EmailCodeResponse(
        message="验证码已发送",
        cooldown_seconds=settings.auth_code_send_interval_seconds,
        debug_code=debug_code,
    )


@router.post("/email/verify-code", response_model=AuthLoginResponse)
def verify_email_code(payload: EmailCodeVerifyRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        user, session = auth_service.verify_email_code(
            db,
            payload.email,
            payload.code,
            ip_address=auth_service.client_ip(request),
            user_agent_value=auth_service.user_agent(request),
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    set_session_cookie(response, session.session_id)
    return AuthLoginResponse(user=AuthUserRead.model_validate(user))


@router.get("/me", response_model=AuthUserRead)
def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/logout", response_model=AuthMessage)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    session = auth_service.get_valid_session(db, request.cookies.get(settings.auth_cookie_name))
    if session is not None:
        auth_service.revoke_session(db, session)
        auth_service.write_audit_log(
            db,
            action="logout",
            success=True,
            user_id=session.user_id,
            ip_address=auth_service.client_ip(request),
            user_agent_value=auth_service.user_agent(request),
        )
    clear_session_cookie(response)
    return AuthMessage(message="已退出登录")


@router.get("/oauth/google/start")
def google_oauth_start():
    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri):
        raise HTTPException(status_code=501, detail="Google 登录暂未配置")
    raise HTTPException(status_code=501, detail="Google 登录接口已预留，待接入 OAuth 回调")


@router.get("/oauth/wechat/start")
def wechat_oauth_start():
    settings = get_settings()
    if not (settings.wechat_app_id and settings.wechat_app_secret and settings.wechat_redirect_uri):
        raise HTTPException(status_code=501, detail="微信登录暂未配置")
    raise HTTPException(status_code=501, detail="微信登录接口已预留，待接入 OAuth 回调")
