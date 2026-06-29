from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.task import ExportRecord, Task, TaskFile, TaskPage, TaskStep
from backend.app.schemas.task import ExportRecordCreate, TaskCreate, TaskFileCreate, TaskPageCreate, TaskStepUpsert, TaskUpdate
from backend.app.services.enums import TaskStatus


STAGE_PROGRESS = {
    "render": 10,
    "layout_detect": 25,
    "layout_refine": 35,
    "ocr": 65,
    "text_cleaning": 78,
    "document_build": 88,
    "export": 100,
    "ai_reading": 100,
}


def generate_task_id() -> str:
    return uuid4().hex


def default_storage_dir(task_id: str) -> str:
    settings = get_settings()
    storage_root = Path(settings.storage_root)
    if not storage_root.is_absolute():
        project_root = Path(__file__).resolve().parents[3]
        storage_root = project_root / storage_root
    return str(storage_root / task_id)


def create_task(db: Session, data: TaskCreate) -> Task:
    task_id = data.task_id or generate_task_id()
    task = Task(
        task_id=task_id,
        original_name=data.original_name,
        input_type=data.input_type.value,
        status=TaskStatus.PENDING.value,
        current_stage=None,
        progress=0,
        storage_dir=data.storage_dir or default_storage_dir(task_id),
        page_count=data.page_count,
        output_format=data.output_format,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, limit: int = 50, offset: int = 0) -> list[Task]:
    statement = select(Task).order_by(Task.created_at.desc()).offset(offset).limit(limit)
    return list(db.execute(statement).scalars().all())


def get_task(db: Session, task_id: str) -> Task | None:
    statement = select(Task).where(Task.task_id == task_id)
    return db.execute(statement).scalar_one_or_none()


def update_task(db: Session, task: Task, data: TaskUpdate) -> Task:
    values = data.model_dump(exclude_unset=True)
    for key, value in values.items():
        if value is None:
            setattr(task, key, None)
        elif key in {"status", "current_stage"}:
            setattr(task, key, value.value)
        else:
            setattr(task, key, value)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def mark_task_processing(db: Session, task: Task, stage: str | None = None, progress: int | None = None) -> Task:
    task.status = TaskStatus.PROCESSING.value
    if stage is not None:
        task.current_stage = stage
    if progress is not None:
        task.progress = progress
    if task.started_at is None:
        task.started_at = datetime.now()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def mark_task_success(db: Session, task: Task) -> Task:
    task.status = TaskStatus.SUCCESS.value
    task.current_stage = None
    task.progress = 100
    task.finished_at = datetime.now()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def mark_task_failed(db: Session, task: Task, stage: str | None, error_message: str) -> Task:
    task.status = TaskStatus.FAILED.value
    task.current_stage = stage
    task.error_message = error_message
    task.finished_at = datetime.now()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def sync_task_from_step(db: Session, task_id: str, step: TaskStep) -> None:
    task = get_task(db, task_id)
    if task is None:
        return

    if step.status == TaskStatus.FAILED.value:
        mark_task_failed(db, task, step.stage, step.error_message or "Task step failed")
        return

    if step.status in {TaskStatus.PROCESSING.value, TaskStatus.SUCCESS.value}:
        stage_base_progress = STAGE_PROGRESS.get(step.stage, task.progress)
        if step.status == TaskStatus.PROCESSING.value:
            progress = min(stage_base_progress, max(task.progress, step.progress))
        else:
            progress = max(task.progress, stage_base_progress)
        mark_task_processing(db, task, stage=step.stage, progress=progress)


def upsert_task_step(db: Session, task_id: str, data: TaskStepUpsert) -> TaskStep:
    statement = select(TaskStep).where(TaskStep.task_id == task_id, TaskStep.stage == data.stage.value)
    step = db.execute(statement).scalar_one_or_none()
    if step is None:
        step = TaskStep(task_id=task_id, stage=data.stage.value)
    step.status = data.status.value
    step.progress = data.progress
    step.duration_ms = data.duration_ms
    step.summary_json = data.summary_json
    step.error_message = data.error_message
    if data.status == TaskStatus.PROCESSING and step.started_at is None:
        step.started_at = datetime.now()
    if data.status in {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.SKIPPED}:
        step.finished_at = datetime.now()
    db.add(step)
    db.commit()
    db.refresh(step)
    sync_task_from_step(db, task_id, step)
    return step


def list_task_steps(db: Session, task_id: str) -> list[TaskStep]:
    statement = select(TaskStep).where(TaskStep.task_id == task_id).order_by(TaskStep.id.asc())
    return list(db.execute(statement).scalars().all())


def add_task_file(db: Session, task_id: str, data: TaskFileCreate) -> TaskFile:
    item = TaskFile(task_id=task_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_task_files(db: Session, task_id: str) -> list[TaskFile]:
    statement = select(TaskFile).where(TaskFile.task_id == task_id).order_by(TaskFile.id.asc())
    return list(db.execute(statement).scalars().all())


def add_task_page(db: Session, task_id: str, data: TaskPageCreate) -> TaskPage:
    item = TaskPage(task_id=task_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_task_pages(db: Session, task_id: str) -> list[TaskPage]:
    statement = select(TaskPage).where(TaskPage.task_id == task_id).order_by(TaskPage.page_no.asc())
    return list(db.execute(statement).scalars().all())


def get_task_page(db: Session, task_id: str, page_no: int) -> TaskPage | None:
    statement = select(TaskPage).where(TaskPage.task_id == task_id, TaskPage.page_no == page_no)
    return db.execute(statement).scalar_one_or_none()


def add_export_record(db: Session, task_id: str, data: ExportRecordCreate) -> ExportRecord:
    values = data.model_dump()
    values["status"] = data.status.value
    item = ExportRecord(task_id=task_id, **values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_export_records(db: Session, task_id: str) -> list[ExportRecord]:
    statement = select(ExportRecord).where(ExportRecord.task_id == task_id).order_by(ExportRecord.id.asc())
    return list(db.execute(statement).scalars().all())


def get_export_record(db: Session, export_id: int) -> ExportRecord | None:
    statement = select(ExportRecord).where(ExportRecord.id == export_id)
    return db.execute(statement).scalar_one_or_none()
