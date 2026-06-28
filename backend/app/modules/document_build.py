#!/usr/bin/env python3
"""读取 clean/document.json，导出 Markdown（从清洗后文档模型生成输出）。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "backend" / "storage" / "tasks"


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_chapters(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for page in pages:
        for block in page.get("blocks", []):
            if block.get("type") == "heading" and block.get("level") == 1:
                current = {
                    "chapter_id": f"ch{len(chapters) + 1:03d}",
                    "title": block["text"],
                    "level": 1,
                    "source_pages": list(block.get("source_pages", [])),
                    "blocks": [],
                }
                chapters.append(current)
                continue
            if current is None:
                current = {
                    "chapter_id": f"ch{len(chapters) + 1:03d}",
                    "title": "正文",
                    "level": 1,
                    "source_pages": [],
                    "blocks": [],
                }
                chapters.append(current)
            current["blocks"].append(block)
            for pn in block.get("source_pages", []):
                if pn not in current["source_pages"]:
                    current["source_pages"].append(pn)

    return chapters


def infer_document_title(pages: list[dict[str, Any]], fallback: str) -> str:
    for page in pages:
        for block in page.get("blocks", []):
            if block.get("role") == "title":
                return block["text"]
    return fallback


def block_to_markdown(block: dict[str, Any]) -> list[str]:
    text = block["text"]
    block_type = block["type"]
    if block_type == "heading":
        level = int(block.get("level", 2))
        level = max(1, min(level, 6))
        return [f"{'#' * level} {text}"]
    if block_type == "caption":
        return [f"> {text}"]
    if block_type == "sidebar":
        return [f"> 补充：{text}"]
    if block_type == "note":
        return [f"> 注：{text}"]
    if block.get("_paragraph_break"):
        return ["", text]
    return [text]


def has_title_block(pages: list[dict[str, Any]]) -> bool:
    for page in pages:
        for block in page.get("blocks", []):
            if block.get("role") == "title":
                return True
    return False


def render_markdown(document: dict[str, Any]) -> str:
    lines: list[str] = []
    first_page = True
    for page in document.get("pages", []):
        lines.append(f"<!-- page {page['page_no']} -->")
        lines.append("")
        for block in page.get("blocks", []):
            # 如果第一个 block 是 title 且文档标题已包含，跳过防止重复
            parts = block_to_markdown(block)
            lines.extend(parts)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_document(task_dir: Path) -> dict[str, Any]:
    doc_path = task_dir / "clean" / "document.json"
    doc = load_json(doc_path)
    pages = doc.get("pages", [])
    title = doc.get("title") or infer_document_title(pages, task_dir.name)
    chapters = build_chapters(pages)
    doc["title"] = title
    doc["chapters"] = chapters
    doc["finished_at"] = datetime.now().isoformat(timespec="seconds")
    return doc


def write_outputs(task_dir: Path, document: dict[str, Any]) -> dict[str, str]:
    clean_dir = task_dir / "clean"
    document_path = clean_dir / "document.json"
    markdown_path = clean_dir / "book.md"
    write_json(document_path, document)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(document), encoding="utf-8")
    return {
        "document_path": project_relative(document_path),
        "markdown_path": project_relative(markdown_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 clean/document.json 导出 Markdown（排版清洗后）。")
    parser.add_argument("task", help="Task ID 或完整路径")
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
        help=f"任务存储根目录，默认: {DEFAULT_STORAGE_ROOT}",
    )
    return parser


def resolve_task_dir(task: str, storage_root: Path) -> Path:
    p = Path(task).expanduser()
    if p.exists():
        return p.resolve()
    return (storage_root / task).resolve()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    task_dir = resolve_task_dir(args.task, Path(args.storage_root).expanduser().resolve())

    try:
        document = build_document(task_dir)
        outputs = write_outputs(task_dir, document)
    except Exception as exc:
        print(f"文档导出失败: {exc}")
        return 1

    stats = document.get("stats", {})
    print(f"导出文档: {document['task_id']}")
    print(f"标题: {document['title']}")
    print(f"页数: {stats.get('page_count', 0)}")
    print(f"输出 block 数: {stats.get('output_blocks', 0)}")
    print(f"Document JSON: {outputs['document_path']}")
    print(f"Markdown: {outputs['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
