from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from backend.app.services.enums import InputType, TaskStage, TaskStatus


class TaskCreate(BaseModel):
    task_id: str | None = None
    original_name: str = Field(..., max_length=255)
    input_type: InputType = InputType.PDF
    output_format: str | None = "markdown,epub"
    storage_dir: str | None = None
    page_count: int | None = None


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    current_stage: TaskStage | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    page_count: int | None = None
    error_message: str | None = None


class TaskRead(BaseModel):
    id: int
    task_id: str
    user_id: int | None
    original_name: str
    input_type: str
    status: str
    current_stage: str | None
    progress: int
    storage_dir: str
    page_count: int | None
    output_format: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskStepUpsert(BaseModel):
    stage: TaskStage
    status: TaskStatus = TaskStatus.PENDING
    progress: int = Field(default=0, ge=0, le=100)
    duration_ms: int | None = None
    summary_json: dict[str, Any] | None = None
    error_message: str | None = None


class TaskStepRead(BaseModel):
    id: int
    task_id: str
    stage: str
    status: str
    progress: int
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    summary_json: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskFileCreate(BaseModel):
    file_role: str
    file_name: str
    file_path: str
    mime_type: str | None = None
    file_size: int | None = None
    page_no: int | None = None


class TaskFileRead(BaseModel):
    id: int
    task_id: str
    file_role: str
    file_name: str
    file_path: str
    mime_type: str | None
    file_size: int | None
    page_no: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskPageCreate(BaseModel):
    page_no: int
    image_path: str
    width: int | None = None
    height: int | None = None
    quality_status: str | None = None
    page_type: str | None = None
    layout_type: str | None = None
    ocr_status: str | None = None
    avg_confidence: Decimal | None = None
    need_review: bool = False


class TaskPageRead(BaseModel):
    id: int
    task_id: str
    page_no: int
    image_path: str
    width: int | None
    height: int | None
    quality_status: str | None
    page_type: str | None
    layout_type: str | None
    ocr_status: str | None
    avg_confidence: Decimal | None
    need_review: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExportRecordCreate(BaseModel):
    format: str
    file_path: str | None = None
    file_size: int | None = None
    status: TaskStatus = TaskStatus.PENDING
    error_message: str | None = None


class ExportRecordRead(BaseModel):
    id: int
    task_id: str
    format: str
    file_path: str | None
    file_size: int | None
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
