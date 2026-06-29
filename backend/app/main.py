from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.exports import router as exports_router
from backend.app.api.health import router as health_router
from backend.app.api.task_events import router as task_events_router
from backend.app.api.tasks import router as tasks_router
from backend.app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(tasks_router)
    app.include_router(exports_router)
    app.include_router(task_events_router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "status": "running"}

    return app


app = create_app()
