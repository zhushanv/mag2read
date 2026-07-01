"""
AI 一键整理服务：收集阅读稿的全部文本块，
将非中文段落后翻译为中文，重新组装为一份
结构清晰、通顺易读的一站式中文文稿。
"""
from __future__ import annotations

import logging
from typing import Any

from backend.app.services.translate_service import translate_blocks

logger = logging.getLogger(__name__)


def _get_block_texts(document: dict[str, Any] | None) -> list[dict[str, Any]]:
    """从清洗文档中提取所有文本块（按阅读顺序）"""
    if not document:
        return []

    blocks: list[dict[str, Any]] = []

    # 支持两层结构：document.blocks 或 document.pages[].blocks
    raw_blocks = document.get("blocks")
    if isinstance(raw_blocks, list):
        for i, block in enumerate(raw_blocks):
            blocks.append({
                "index": i,
                "text": block.get("text", ""),
                "type": block.get("type", "paragraph"),
                "role": block.get("role", "body"),
                "level": block.get("level"),
                "page_no": block.get("page_no"),
                "is_graphical": block.get("is_graphical", False),
            })
        return blocks

    pages = document.get("pages", [])
    for page in pages:
        page_no = page.get("page_no")
        for i, block in enumerate(page.get("blocks", [])):
            blocks.append({
                "index": i,
                "text": block.get("text", ""),
                "type": block.get("type", "paragraph"),
                "role": block.get("role", "body"),
                "level": block.get("level"),
                "page_no": page_no,
                "is_graphical": block.get("is_graphical", False),
            })
    return blocks


def _heading_prefix(level: int | None) -> str:
    """根据标题层级返回 markdown 样式前缀"""
    if level is None or level < 1:
        return "###"
    if level == 1:
        return "#"
    if level == 2:
        return "##"
    return "###"


def _filter_and_sort_blocks(blocks: list[dict[str, Any]], include_media: bool = False) -> list[dict[str, Any]]:
    """过滤空文本和噪音，保留正文排版顺序"""
    result = []
    for block in blocks:
        text = (block.get("text") or "").strip()
        if block.get("is_graphical") and not include_media:
            continue
        if block.get("role") in ("header", "footer", "page_number"):
            continue
        if not text:
            continue
        if block.get("type") in ("noise",):
            continue
        result.append(block)
    return result


async def polish_document(
    document: dict[str, Any] | None,
    include_media: bool = False,
) -> dict[str, Any]:
    """
    一键整理核心逻辑：
    1. 提取所有非噪音文本块
    2. 检测非中文段落 → 翻译
    3. 按照标题层级重新组装
    4. 返回整理结果以及统计信息
    """
    raw_blocks = _get_block_texts(document)
    blocks = _filter_and_sort_blocks(raw_blocks, include_media)

    total = len(blocks)
    if total == 0:
        return {
            "content": "文档内容为空，无法整理。",
            "stats": {"total_blocks": 0, "translated": 0, "characters": 0},
        }

    # 收集所有文本
    texts = [b["text"] for b in blocks]

    # 批量翻译非中文文本
    translations = await translate_blocks(texts)

    # 组装整理文稿
    lines: list[str] = []
    translated_count = 0
    for i, block in enumerate(blocks):
        text = texts[i]
        trans = translations[i]

        role = block.get("role", "body")
        btype = block.get("type", "paragraph")
        level = block.get("level")

        is_heading = (btype == "heading" or role in ("title", "heading"))
        is_caption = (btype == "caption" or role == "caption")
        is_note = (btype == "note" or role == "note")
        is_formula = (btype == "formula" or role == "formula")

        if is_heading:
            prefix = _heading_prefix(level)
            lines.append("")
            lines.append(f"{prefix} {text}")
            lines.append("")
            if trans:
                lines.append(f"> 📖 {trans}")
                lines.append("")
                translated_count += 1
        elif is_caption:
            lines.append(f"> *{text}*")
            if trans:
                lines.append(f"> 📖 *{trans}*")
                translated_count += 1
        elif is_note:
            lines.append(f"> {text}")
            if trans:
                lines.append(f"> 📖 {trans}")
                translated_count += 1
        elif is_formula:
            lines.append(f"`{text}`")
        else:
            lines.append(text)
            if trans:
                lines.append(f"  📖 _{trans}_")
                translated_count += 1

    content = "\n".join(lines)
    char_count = len(content.replace("\n", "").replace(" ", ""))

    return {
        "content": content,
        "stats": {
            "total_blocks": total,
            "translated": translated_count,
            "characters": char_count,
        },
    }
