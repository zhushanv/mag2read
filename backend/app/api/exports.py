from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services import task_service


router = APIRouter(prefix="/api/exports", tags=["exports"])

PREVIEW_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm", ".json"}
PREVIEW_FALLBACK_TEXT = "该格式为二进制文件，暂不支持在线预览，请下载后查看。"


@router.get("/{export_id}/download")
def download_export(export_id: int, db: Session = Depends(get_db)) -> FileResponse:
    record = task_service.get_export_record(db, export_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Export record not found")
    if not record.file_path:
        raise HTTPException(status_code=404, detail="Export file is not available")

    file_path = Path(record.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found on disk")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/{export_id}/preview", response_class=PlainTextResponse)
def preview_export(export_id: int, limit: int = 6000, db: Session = Depends(get_db)) -> PlainTextResponse:
    record = task_service.get_export_record(db, export_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Export record not found")
    if not record.file_path:
        raise HTTPException(status_code=404, detail="Export file is not available")

    file_path = Path(record.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found on disk")
    if file_path.suffix.lower() not in PREVIEW_SUFFIXES:
        return PlainTextResponse(PREVIEW_FALLBACK_TEXT)

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    return PlainTextResponse(content[: max(500, min(limit, 20000))])
