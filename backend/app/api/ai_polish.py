from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.auth_dependencies import get_current_user
from backend.app.core.database import get_db
from backend.app.models.task import User
from backend.app.modules.edited_document import load_editable_document
from backend.app.services.ai_polish_service import polish_document

router = APIRouter(prefix="/api/tasks", tags=["ai"])


class PolishResponse(BaseModel):
    content: str
    stats: dict


@router.post("/{task_id}/polish", response_model=PolishResponse)
async def ai_polish(
    task_id: str,
    include_media: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """一键整理：将阅读稿的非中文文本翻译为中文并重新整理。"""
    document = load_editable_document(task_id, user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档未找到")
    result = await polish_document(document, include_media)
    return PolishResponse(**result)
