from __future__ import annotations

import base64
import re
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session

from backend.app.core.auth_dependencies import get_current_user
from backend.app.core.database import get_db
from backend.app.models.task import User
from backend.app.services import task_service


router = APIRouter(prefix="/api/exports", tags=["exports"])

PREVIEW_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm", ".json"}
PREVIEW_FALLBACK_TEXT = "该格式为二进制文件，暂不支持在线预览，请下载后查看。"
EMBED_MEDIA_SUFFIXES = {".html", ".htm", ".md", ".markdown"}
PACKAGE_MEDIA_SUFFIXES = EMBED_MEDIA_SUFFIXES
MEDIA_FILE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def ensure_export_owner(record, current_user: User, db: Session):
    task = task_service.get_task(db, record.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No permission")
    return task


def image_data_uri(path: Path) -> str | None:
    if not path.is_file():
        return None
    suffix = path.suffix.lower()
    mime_type = "image/png"
    if suffix in {".jpg", ".jpeg"}:
        mime_type = "image/jpeg"
    elif suffix == ".webp":
        mime_type = "image/webp"
    elif suffix == ".gif":
        mime_type = "image/gif"
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def embed_download_media(content: str, task_dir: Path) -> str:
    media_dir = task_dir / "media"

    def replace(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        filename = Path(match.group("filename")).name
        uri = image_data_uri(media_dir / filename)
        return f"{prefix}{uri}" if uri else match.group(0)

    return re.sub(
        r"(?P<prefix>(?:src=|]\()\s*[\"']?)(?:\.\./)?media/(?P<filename>[^\"')\s]+)",
        replace,
        content,
    )


def package_download_media(content: str, task_dir: Path) -> tuple[str, list[Path]]:
    media_dir = task_dir / "media"
    media_paths: dict[str, Path] = {}

    def replace(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        filename = Path(match.group("filename")).name
        path = media_dir / filename
        if path.is_file():
            media_paths[filename] = path
        return f"{prefix}media/{filename}"

    rewritten = re.sub(
        r"(?P<prefix>(?:src=|]\()\s*[\"']?)(?:\.\./)?media/(?P<filename>[^\"')\s]+)",
        replace,
        content,
    )
    return rewritten, list(media_paths.values())


def build_export_zip(file_path: Path, task_dir: Path) -> tuple[bytes, str]:
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    packaged_content, media_paths = package_download_media(content, task_dir)
    document_name = "document.html" if file_path.suffix.lower() in {".html", ".htm"} else "document.md"
    zip_name = f"{file_path.stem}-{file_path.suffix.lower().lstrip('.')}-resources.zip"

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(document_name, packaged_content)
        used_names: set[str] = set()
        for path in media_paths:
            name = path.name
            if name in used_names:
                continue
            used_names.add(name)
            archive.write(path, f"media/{name}")
    return buffer.getvalue(), zip_name


@router.get("/{export_id}/download")
def download_export(
    export_id: int,
    mode: str = Query(default="package"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = task_service.get_export_record(db, export_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Export record not found")
    if not record.file_path:
        raise HTTPException(status_code=404, detail="Export file is not available")
    task = ensure_export_owner(record, current_user, db)

    file_path = Path(record.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found on disk")
    suffix = file_path.suffix.lower()
    if suffix in PACKAGE_MEDIA_SUFFIXES and mode != "single":
        content, filename = build_export_zip(file_path, Path(task.storage_dir))
        return Response(
            content=content,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if suffix in EMBED_MEDIA_SUFFIXES:
        content = embed_download_media(file_path.read_text(encoding="utf-8", errors="ignore"), Path(task.storage_dir))
        media_type = "text/html; charset=utf-8" if suffix in {".html", ".htm"} else "text/markdown; charset=utf-8"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{file_path.name}"'},
        )

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/{export_id}/preview", response_class=PlainTextResponse)
def preview_export(export_id: int, limit: int = 6000, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PlainTextResponse:
    record = task_service.get_export_record(db, export_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Export record not found")
    if not record.file_path:
        raise HTTPException(status_code=404, detail="Export file is not available")
    ensure_export_owner(record, current_user, db)

    file_path = Path(record.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found on disk")
    if file_path.suffix.lower() not in PREVIEW_SUFFIXES:
        return PlainTextResponse(PREVIEW_FALLBACK_TEXT)

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    return PlainTextResponse(content[: max(500, min(limit, 20000))])
