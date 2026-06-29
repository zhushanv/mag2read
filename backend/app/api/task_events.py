from __future__ import annotations

import asyncio
import json
from hashlib import sha1

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.core.database import SessionLocal
from backend.app.schemas.task import TaskRead, TaskStepRead
from backend.app.services import task_service
from backend.app.services.enums import TaskStatus


router = APIRouter(tags=["task-events"])

TERMINAL_STATUSES = {
    TaskStatus.SUCCESS.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
}


@router.websocket("/ws/tasks/{task_id}")
async def watch_task(websocket: WebSocket, task_id: str):
    await websocket.accept()
    last_signature = ""

    try:
        while True:
            payload = build_task_event(task_id)
            if payload is None:
                await websocket.send_text(json.dumps({"type": "task_missing", "task_id": task_id}))
                await websocket.close(code=1008)
                return

            signature = event_signature(payload)
            if signature != last_signature:
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                last_signature = signature

            if payload["task"]["status"] in TERMINAL_STATUSES:
                await websocket.close(code=1000)
                return

            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        return


def build_task_event(task_id: str) -> dict | None:
    db = SessionLocal()
    try:
        task = task_service.get_task(db, task_id)
        if task is None:
            return None
        steps = task_service.list_task_steps(db, task_id)
        return {
            "type": "task_update",
            "task": TaskRead.model_validate(task).model_dump(mode="json"),
            "steps": [TaskStepRead.model_validate(step).model_dump(mode="json") for step in steps],
        }
    finally:
        db.close()


def event_signature(payload: dict) -> str:
    task = payload["task"]
    steps = payload["steps"]
    compact = {
        "task": {
            "status": task["status"],
            "current_stage": task["current_stage"],
            "progress": task["progress"],
            "page_count": task["page_count"],
            "error_message": task["error_message"],
            "updated_at": task["updated_at"],
            "finished_at": task["finished_at"],
        },
        "steps": [
            {
                "stage": step["stage"],
                "status": step["status"],
                "progress": step["progress"],
                "duration_ms": step["duration_ms"],
                "error_message": step["error_message"],
                "updated_at": step["updated_at"],
            }
            for step in steps
        ],
    }
    return sha1(json.dumps(compact, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
