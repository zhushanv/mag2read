from __future__ import annotations

from backend.app.workers.celery_app import celery_app


@celery_app.task(name="stage0.ping")
def ping() -> str:
    return "pong"
