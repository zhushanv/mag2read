from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.models.task import User
from backend.app.services import auth_service


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    settings = get_settings()
    session = auth_service.get_valid_session(db, request.cookies.get(settings.auth_cookie_name))
    if session is None:
        return None
    user = auth_service.get_user(db, session.user_id)
    if user is None or user.status != "active":
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_optional_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
