from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.app.core.auth_dependencies import get_current_user
from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.models.task import User
from backend.app.modules.edited_document import load_editable_document, reset_edited_document, save_edited_document
from backend.app.schemas.task import (
    ExportRecordRead,
    TaskCreate,
    TaskFileCreate,
    TaskFileRead,
    TaskPageRead,
    TaskRead,
    TaskStepRead,
    TaskStepUpsert,
    TaskUpdate,
)
from backend.app.services import task_service
from backend.app.services.enums import InputType
from io import BytesIO
from PIL import Image


router = APIRouter(prefix="/api/tasks", tags=["tasks"])

SUPPORTED_UPLOAD_SUFFIXES = {
    ".pdf": InputType.PDF,
    ".jpg": InputType.IMAGE,
    ".jpeg": InputType.IMAGE,
    ".png": InputType.IMAGE,
}
SUPPORTED_PROCESSING_MODES = {"local", "cloud", "auto"}


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[\x00-\x1f]", "", name)
    return name or "uploaded_file"


def input_type_from_filename(filename: str) -> InputType:
    suffix = Path(filename).suffix.lower()
    input_type = SUPPORTED_UPLOAD_SUFFIXES.get(suffix)
    if input_type is None:
        allowed = ", ".join(sorted(SUPPORTED_UPLOAD_SUFFIXES))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")
    return input_type


def file_role_for_input_type(input_type: InputType) -> str:
    if input_type == InputType.PDF:
        return "input_pdf"
    return "input_image"


def ensure_task(db: Session, task_id: str):
    task = task_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def ensure_user_task(db: Session, task_id: str, current_user: User):
    task = ensure_task(db, task_id)
    if task.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No permission")
    return task


def task_file_path(task, *parts: str) -> Path:
    path = (Path(task.storage_dir).resolve() / Path(*parts)).resolve()
    task_dir = Path(task.storage_dir).resolve()
    if path != task_dir and task_dir not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid task file path")
    return path


def read_task_json(task, *parts: str):
    path = task_file_path(task, *parts)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {'/'.join(parts)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON file: {path.name}") from exc


def write_task_metadata(task_dir: Path, values: dict) -> None:
    metadata_path = task_dir / "metadata.json"
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}
    else:
        metadata = {}
    metadata.update(values)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("", response_model=TaskRead)
def create_task(data: TaskCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data.user_id = current_user.id
    return task_service.create_task(db, data)


@router.post("/upload", response_model=TaskRead)
async def upload_task_file(
    file: UploadFile = File(...),
    output_format: str = Form(default="epub,markdown,docx"),
    processing_mode: str = Form(default="auto"),
    task_id: str | None = Form(default=None),
    auto_start: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    original_name = safe_filename(file.filename or "uploaded_file")
    input_type = input_type_from_filename(original_name)
    processing_mode = processing_mode.strip().lower()
    if processing_mode not in SUPPORTED_PROCESSING_MODES:
        allowed = ", ".join(sorted(SUPPORTED_PROCESSING_MODES))
        raise HTTPException(status_code=400, detail=f"Unsupported processing mode. Allowed: {allowed}")

    if task_id and task_service.get_task(db, task_id):
        raise HTTPException(status_code=409, detail="Task ID already exists")

    task = task_service.create_task(
        db,
        TaskCreate(
            task_id=task_id,
            user_id=current_user.id,
            original_name=original_name,
            input_type=input_type,
            output_format=output_format,
        ),
    )

    task_dir = Path(task.storage_dir)
    input_dir = task_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    target_path = input_dir / original_name

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    written = 0
    try:
        with target_path.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    target_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File is larger than {settings.max_upload_size_mb} MB",
                    )
                output.write(chunk)
    finally:
        await file.close()

    task_service.add_task_file(
        db,
        task.task_id,
        TaskFileCreate(
            file_role=file_role_for_input_type(input_type),
            file_name=original_name,
            file_path=str(target_path),
            mime_type=file.content_type,
            file_size=written,
            page_no=None,
        ),
    )
    write_task_metadata(
        task_dir,
        {
            "task_id": task.task_id,
            "original_name": original_name,
            "input_type": input_type.value,
            "output_format": output_format,
            "processing_mode": processing_mode,
            "processing_mode_requested": processing_mode,
            "metadata_updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    if auto_start:
        from backend.app.workers.tasks import process_uploaded_task

        process_uploaded_task.delay(task.task_id)
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = None if current_user.role == "admin" else current_user.id
    return task_service.list_tasks(db, limit=limit, offset=offset, user_id=user_id)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ensure_user_task(db, task_id, current_user)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: str, data: TaskUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = ensure_user_task(db, task_id, current_user)
    return task_service.update_task(db, task, data)


@router.get("/{task_id}/steps", response_model=list[TaskStepRead])
def list_task_steps(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_user_task(db, task_id, current_user)
    return task_service.list_task_steps(db, task_id)


@router.get("/{task_id}/files", response_model=list[TaskFileRead])
def list_task_files(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_user_task(db, task_id, current_user)
    return task_service.list_task_files(db, task_id)


@router.get("/{task_id}/pages", response_model=list[TaskPageRead])
def list_task_pages(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_user_task(db, task_id, current_user)
    return task_service.list_task_pages(db, task_id)


@router.get("/{task_id}/pages/{page_no}", response_model=TaskPageRead)
def get_task_page(task_id: str, page_no: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_user_task(db, task_id, current_user)
    page = task_service.get_task_page(db, task_id, page_no)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/{task_id}/pages/{page_no}/image")
def get_task_page_image(task_id: str, page_no: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_user_task(db, task_id, current_user)
    page = task_service.get_task_page(db, task_id, page_no)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    path = Path(page.image_path).resolve()
    task_dir = Path(page.image_path).resolve()
    if not path.exists():
        task = ensure_user_task(db, task_id, current_user)
        path = task_file_path(task, "pages", f"page_{page_no:03d}.png")
        task_dir = Path(task.storage_dir).resolve()
    else:
        task = ensure_user_task(db, task_id, current_user)
        task_dir = Path(task.storage_dir).resolve()

    if path != task_dir and task_dir not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid page image path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(path, media_type="image/png", filename=path.name)


@router.get("/{task_id}/pages/{page_no}/layout")
def get_task_page_layout(task_id: str, page_no: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = ensure_user_task(db, task_id, current_user)
    return read_task_json(task, "layout", f"page_{page_no:03d}.json")


@router.get("/{task_id}/pages/{page_no}/ocr")
def get_task_page_ocr(task_id: str, page_no: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = ensure_user_task(db, task_id, current_user)
    return read_task_json(task, "ocr", f"page_{page_no:03d}.json")


@router.get("/{task_id}/clean-document")
def get_clean_document(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = ensure_user_task(db, task_id, current_user)
    return read_task_json(task, "clean", "document.json")


@router.get("/{task_id}/edited-document")
def get_edited_document(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = ensure_user_task(db, task_id, current_user)
    try:
        return load_editable_document(Path(task.storage_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Invalid editable document JSON") from exc


@router.put("/{task_id}/edited-document")
def put_edited_document(
    task_id: str,
    payload: dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_user_task(db, task_id, current_user)
    try:
        return save_edited_document(Path(task.storage_dir), payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Invalid existing edited document JSON") from exc


@router.post("/{task_id}/edited-document/reset")
def post_reset_edited_document(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = ensure_user_task(db, task_id, current_user)
    try:
        return reset_edited_document(Path(task.storage_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Invalid clean document JSON") from exc


@router.get("/{task_id}/pages/{page_no}/crop")
def get_task_page_crop(
    task_id: str,
    page_no: int,
    x1: float = Query(..., description="Left coordinate"),
    y1: float = Query(..., description="Top coordinate"),
    x2: float = Query(..., description="Right coordinate"),
    y2: float = Query(..., description="Bottom coordinate"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the cropped image region from a task page.

    Coordinates are in the original page image space.
    """
    task = ensure_user_task(db, task_id, current_user)
    page = task_service.get_task_page(db, task_id, page_no)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    # Resolve page image path
    path = Path(page.image_path).resolve() if page.image_path else None
    if path is None or not path.exists():
        path = task_file_path(task, "pages", f"page_{page_no:03d}.png")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page image not found")

    try:
        img = Image.open(path)
        # Clamp coordinates to image bounds
        img_w, img_h = img.size
        left = max(0, min(x1, x2, img_w - 1))
        upper = max(0, min(y1, y2, img_h - 1))
        right = min(max(x1, x2, left + 1), img_w)
        lower = min(max(y1, y2, upper + 1), img_h)
        crop = img.crop((left, upper, right, lower))
        buf = BytesIO()
        crop.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to crop image: {exc}")


@router.get("/{task_id}/media/{filename}")
def get_task_media(
    task_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_user_task(db, task_id, current_user)
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.lower().endswith(".png"):
        raise HTTPException(status_code=400, detail="Invalid media filename")
    path = task_file_path(task, "media", safe_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(path, media_type="image/png", filename=safe_name)


@router.get("/{task_id}/exports", response_model=list[ExportRecordRead])
def list_task_exports(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_user_task(db, task_id, current_user)
    return task_service.list_export_records(db, task_id)


@router.put("/{task_id}/steps", response_model=TaskStepRead)
def upsert_task_step(task_id: str, data: TaskStepUpsert, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    ensure_task(db, task_id)
    return task_service.upsert_task_step(db, task_id, data)
