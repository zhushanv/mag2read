from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services.translate_service import translate_blocks, translate_text

router = APIRouter(prefix="/api/translate", tags=["translate"])


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str = "zh"


class BatchTranslateRequest(BaseModel):
    texts: list[str]
    source_lang: str = "auto"
    target_lang: str = "zh"


class TranslateResponse(BaseModel):
    translated: str | None


class BatchTranslateResponse(BaseModel):
    translated: list[str | None]


@router.post("", response_model=TranslateResponse)
async def translate_single(request: TranslateRequest):
    """翻译单条文本。如果文本主要是中文则返回 null。"""
    result = await translate_text(request.text, request.source_lang, request.target_lang)
    return TranslateResponse(translated=result)


@router.post("/batch", response_model=BatchTranslateResponse)
async def translate_batch(request: BatchTranslateRequest):
    """批量翻译文本块。"""
    results = await translate_blocks(request.texts, request.source_lang, request.target_lang)
    return BatchTranslateResponse(translated=results)
