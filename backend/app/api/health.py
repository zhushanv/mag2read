from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.database import check_database
from backend.app.core.redis_client import check_redis


router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health_check() -> dict[str, object]:
    database = check_database()
    redis = check_redis()
    overall = "ok" if database["ok"] and redis["ok"] else "degraded"
    return {
        "status": overall,
        "services": {
            "api": {"ok": True, "message": "FastAPI is running"},
            "database": database,
            "redis": redis,
        },
    }
