#!/usr/bin/env python3
"""
从 clean/document.json 导出多种格式：EPUB、DOCX、TXT、HTML。

用法:
  conda run -n industrial-cv python backend/scripts/export_document.py DDCPC_sample --formats epub,docx,txt,html
  conda run -n industrial-cv python backend/scripts/export_document.py DDCPC_sample --formats epub  (默认)
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ebooklib import epub
from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from jinja2 import Template


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "backend" / "storage" / "tasks"


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_task_dir(task: str, storage_root: Path) -> Path:
    p = Path(task).expanduser()
    if p.exists():
        return p.resolve()
    return (storage_root / task).resolve()


# ---------------------------------------------------------------
# 读取清洗后文档
# ---------------------------------------------------------------

def load_document(task_dir: Path) -> dict[str, Any]:
    doc_path = task_dir / "clean" / "document.json"
    if not doc_path.exists():
        raise FileNotFoundError(f"请先运行 clean_text.py: {doc_path}")
    return load_json(doc_path)


# ---------------------------------------------------------------
# 通用文本工具
# ---------------------------------------------------------------

def strip_title_newlines(text: str) -> str:
    """将标题中的换行替换为空格，使标题在一行显示。"""
    return re.sub(r"\s*\n\s*", " ", text).strip()


def iter_blocks(document: dict[str, Any]):
    """遍历文档中所有页面和 block。"""
    for page in document.get("pages", []):
        page_no = page["page_no"]
        for block in page.get("blocks", []):
            yield page_no, block


# ---------------------------------------------------------------
# EPUB 导出
# ---------------------------------------------------------------

def export_epub(document: dict[str, Any], output_path: Path) -> str:
    title = strip_title_newlines(document.get("title", "Untitled"))
    author = document.get("author", "")
    language = document.get("language", "zh-CN")

    book = epub.EpubBook()
    book.set_identifier(f"mag2read-{document.get('task_id', 'unknown')}")
    book.set_title(title)
    book.set_language(language)
    if author:
        book.add_author(author)

    # 添加样式
    style = """
    body { font-family: serif; line-height: 1.8; margin: 1em; }
    h1 { font-size: 1.6em; margin-top: 1.5em; margin-bottom: 0.5em; }
    h2 { font-size: 1.3em; margin-top: 1.2em; margin-bottom: 0.4em; }
    h3 { font-size: 1.1em; margin-top: 1em; margin-bottom: 0.3em; }
    p { text-indent: 2em; margin: 0.5em 0; }
    p.no-indent { text-indent: 0; }
    blockquote {
        margin: 0.5em 1em; padding: 0.5em 1em;
        border-left: 3px solid #ccc; color: #555;
        font-style: italic;
    }
    .caption { font-size: 0.9em; color: #666; margin: 0.3em 0; }
    .sidebar { background: #f5f5f5; padding: 0.5em 1em; margin: 0.5em 0; border-radius: 4px; }
    """
    css = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=style,
    )
    book.add_item(css)

    chapters_epub: list[epub.EpubHtml] = []
    spine = ["nav"]

    # 按 chapter 组织（如果有 chapters），否则按 page
    chapters_data = document.get("chapters", [])

    if chapters_data:
        for ch in chapters_data:
            ch_title = strip_title_newlines(ch.get("title", "Untitled"))
            content_parts: list[str] = [
                f'<h1>{_escape_html(ch_title)}</h1>'
            ]
            for block in ch.get("blocks", []):
                content_parts.append(_block_to_html(block))
            html_content = _wrap_html(ch_title, "\n".join(content_parts), style_ref="style.css")
            chapter = epub.EpubHtml(
                title=ch_title,
                file_name=f"chap_{ch['chapter_id']}.xhtml",
                lang=language,
            )
            chapter.content = html_content
            chapter.add_item(css)
            book.add_item(chapter)
            chapters_epub.append(chapter)
            spine.append(chapter)
    else:
        # 无章节结构，按 page 组织
        for page in document.get("pages", []):
            page_no = page["page_no"]
            content_parts: list[str] = []
            for block in page.get("blocks", []):
                content_parts.append(_block_to_html(block))
            html_content = _wrap_html(
                f"Page {page_no}",
                "\n".join(content_parts),
                style_ref="style.css",
            )
            chapter = epub.EpubHtml(
                title=f"Page {page_no}",
                file_name=f"page_{page_no:03d}.xhtml",
                lang=language,
            )
            chapter.content = html_content
            chapter.add_item(css)
            book.add_item(chapter)
            chapters_epub.append(chapter)
            spine.append(chapter)

    book.toc = chapters_epub
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(str(output_path), book)
    return str(output_path)


def _block_to_html(block: dict[str, Any]) -> str:
    block_type = block.get("type", "paragraph")
    text = _escape_html(block["text"])
    is_para_break = block.get("_paragraph_break", False)

    if block_type == "heading":
        level = min(int(block.get("level", 2)), 6)
        return f"<h{level}>{text}</h{level}>"
    if block_type == "caption":
        return f'<blockquote class="caption">{text}</blockquote>'
    if block_type == "sidebar":
        return f'<div class="sidebar"><strong>补充：</strong>{text}</div>'
    if block_type == "note":
        return f'<div class="sidebar"><strong>注：</strong>{text}</div>'
    # paragraph
    indent_class = "" if is_para_break else ' class="no-indent"'
    return f"<p{indent_class}>{text}</p>"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _wrap_html(title: str, body: str, style_ref: str = "style.css") -> str:
    return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta charset="utf-8"/><title>{_escape_html(title)}</title>
<link rel="stylesheet" type="text/css" href="{style_ref}"/></head>
<body>{body}</body>
</html>"""


# ---------------------------------------------------------------
# DOCX 导出
# ---------------------------------------------------------------

def export_docx(document: dict[str, Any], output_path: Path) -> str:
    doc = Document()

    # 页面设置
    section = doc.sections[0]
    section.page_width = Cm(16)
    section.page_height = Cm(24)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)

    # 默认字体
    style = doc.styles["Normal"]
    font = style.font
    font.name = "宋体"
    font.size = Pt(11)
    pf = style.paragraph_format
    pf.line_spacing = 1.5

    # 标题
    title = strip_title_newlines(document.get("title", "Untitled"))
    title_para = doc.add_heading(title, level=1)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 正文
    chapters_data = document.get("chapters", [])
    if chapters_data:
        for ch in chapters_data:
            ch_title = strip_title_newlines(ch.get("title", ""))
            if ch_title:
                doc.add_heading(ch_title, level=1)
            for block in ch.get("blocks", []):
                _add_block_to_docx(doc, block)
    else:
        for page in document.get("pages", []):
            for block in page.get("blocks", []):
                _add_block_to_docx(doc, block)

    doc.save(str(output_path))
    return str(output_path)


def _add_block_to_docx(doc: Document, block: dict[str, Any]) -> None:
    block_type = block.get("type", "paragraph")
    text = block["text"]
    is_para_break = block.get("_paragraph_break", False)

    if block_type == "heading":
        level = min(int(block.get("level", 2)), 6)
        p = doc.add_heading(text, level=level)
    elif block_type == "caption":
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.font.size = Pt(10)
        run.font.italic = True
        p.paragraph_format.left_indent = Cm(0.75)
    elif block_type in ("sidebar", "note"):
        prefix = "补充： " if block_type == "sidebar" else "注： "
        p = doc.add_paragraph()
        run = p.add_run(prefix + text)
        run.font.size = Pt(10)
        run.font.color.rgb = None  # type: ignore  # keep default
        p.paragraph_format.left_indent = Cm(0.5)
    else:
        p = doc.add_paragraph(text)
        if is_para_break:
            p.paragraph_format.first_line_indent = Cm(0.75)


# ---------------------------------------------------------------
# TXT 导出
# ---------------------------------------------------------------

def export_txt(document: dict[str, Any], output_path: Path) -> str:
    lines: list[str] = []

    title = strip_title_newlines(document.get("title", "Untitled"))
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    chapters_data = document.get("chapters", [])
    if chapters_data:
        for ch in chapters_data:
            ch_title = strip_title_newlines(ch.get("title", ""))
            if ch_title:
                lines.append(ch_title)
                lines.append("-" * len(ch_title))
                lines.append("")
            for block in ch.get("blocks", []):
                _add_block_to_txt(lines, block)
    else:
        for page in document.get("pages", []):
            lines.append(f"--- Page {page['page_no']} ---")
            lines.append("")
            for block in page.get("blocks", []):
                _add_block_to_txt(lines, block)

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


def _add_block_to_txt(lines: list[str], block: dict[str, Any]) -> None:
    text = block["text"]
    block_type = block.get("type", "paragraph")

    if block_type == "heading":
        level = int(block.get("level", 2))
        marker = "#" * level
        lines.append(f"{marker} {text}")
    elif block_type == "caption":
        lines.append(f"> {text}")
    elif block_type == "sidebar":
        lines.append(f"> 补充：{text}")
    elif block_type == "note":
        lines.append(f"> 注：{text}")
    else:
        if block.get("_paragraph_break"):
            lines.append("")
        lines.append(text)
    lines.append("")


# ---------------------------------------------------------------
# HTML 导出（独立文件，便于浏览器预览）
# ---------------------------------------------------------------

HTML_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<style>
  body { font-family: 'Noto Serif', 'Source Han Serif SC', Georgia, serif;
         max-width: 720px; margin: 2em auto; padding: 0 1em;
         line-height: 1.9; color: #222; }
  h1 { font-size: 1.5em; margin-top: 1.2em; margin-bottom: 0.6em;
       border-bottom: 2px solid #ddd; padding-bottom: 0.3em; }
  h2 { font-size: 1.25em; margin-top: 1em; margin-bottom: 0.4em; }
  h3 { font-size: 1.1em; margin-top: 0.8em; margin-bottom: 0.3em; }
  p { text-indent: 2em; margin: 0.4em 0; }
  p.no-indent { text-indent: 0; }
  blockquote { margin: 0.5em 1em; padding: 0.3em 1em;
               border-left: 3px solid #aaa; color: #555; }
  blockquote.caption { font-style: italic; font-size: 0.9em; }
  .sidebar { background: #f5f5f5; padding: 0.5em 1em;
             border-radius: 4px; margin: 0.5em 0; font-size: 0.95em; }
  .page-marker { text-align: center; color: #999; font-size: 0.85em;
                 margin: 1.5em 0; border-top: 1px dashed #ddd;
                 padding-top: 0.5em; }
  hr { border: none; border-top: 1px solid #eee; margin: 1.5em 0; }
</style>
</head>
<body>
  <h1>{{ title }}</h1>
  {% if author %}<p style="text-align:center;color:#666;">{{ author }}</p>{% endif %}
  {% if summary %}<blockquote><p>{{ summary }}</p></blockquote>{% endif %}
  {% for page in pages %}
  <div class="page-marker">— Page {{ page.page_no }} —</div>
  {% for block in page.blocks %}
    {{ block_html(block) }}
  {% endfor %}
  {% endfor %}
</body>
</html>""")


HTML_BLOCK_MAP = {
    "heading": lambda b: f"<h{min(b.get('level', 2), 6)}>{_escape_html(b['text'])}</h{min(b.get('level', 2), 6)}>",
    "caption": lambda b: f'<blockquote class="caption">{_escape_html(b["text"])}</blockquote>',
    "sidebar": lambda b: f'<div class="sidebar"><strong>补充：</strong>{_escape_html(b["text"])}</div>',
    "note": lambda b: f'<div class="sidebar"><strong>注：</strong>{_escape_html(b["text"])}</div>',
}


def _html_for_block(block: dict[str, Any]) -> str:
    block_type = block.get("type", "paragraph")
    renderer = HTML_BLOCK_MAP.get(block_type)
    if renderer:
        return renderer(block)
    text = _escape_html(block["text"])
    cls = "" if block.get("_paragraph_break") else ' class="no-indent"'
    return f"<p{cls}>{text}</p>"


def export_html(document: dict[str, Any], output_path: Path) -> str:
    title = strip_title_newlines(document.get("title", "Untitled"))
    author = document.get("author", "")
    summary = document.get("summary", "")
    pages = document.get("pages", [])

    html = HTML_TEMPLATE.render(
        title=title,
        author=author,
        summary=summary,
        lang=document.get("language", "zh-CN"),
        pages=pages,
        block_html=_html_for_block,
    )
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


# ---------------------------------------------------------------
# 统一导出入口
# ---------------------------------------------------------------

FORMAT_EXPORTERS = {
    "epub": ("EPUB 电子书", export_epub, ".epub"),
    "docx": ("Word 文档", export_docx, ".docx"),
    "txt": ("纯文本", export_txt, ".txt"),
    "html": ("HTML 网页", export_html, ".html"),
}


def run_export(task_dir: Path, formats: list[str]) -> dict[str, str]:
    document = load_document(task_dir)
    output_dir = task_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}

    for fmt in formats:
        if fmt not in FORMAT_EXPORTERS:
            print(f"  跳过未知格式: {fmt}")
            continue
        label, exporter, suffix = FORMAT_EXPORTERS[fmt]
        output_path = output_dir / f"{task_dir.name}{suffix}"
        try:
            out = exporter(document, output_path)
            results[fmt] = project_relative(Path(out))
            print(f"  {label:10s} → {project_relative(Path(out))}")
        except Exception as exc:
            print(f"  {label:10s} ✗ 失败: {exc}")

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 clean/document.json 导出多种格式")
    parser.add_argument("task", help="Task ID 或完整路径")
    parser.add_argument(
        "--formats", "-f",
        default="epub",
        help="导出格式，逗号分隔。可选: epub,docx,txt,html。默认: epub",
    )
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    task_dir = resolve_task_dir(args.task, Path(args.storage_root).expanduser().resolve())
    formats = [fmt.strip().lower() for fmt in args.formats.split(",") if fmt.strip()]

    print(f"导出任务: {task_dir.name}")
    print(f"目标格式: {', '.join(formats)}")
    results = run_export(task_dir, formats)

    if not results:
        print("没有成功导出的文件。")
        return 1

    print(f"\n导出完成，共 {len(results)} 个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
