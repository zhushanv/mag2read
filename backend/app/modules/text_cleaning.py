#!/usr/bin/env python3
"""
排版噪声清洗模块

按以下流水线清洗 OCR 结果：
  OcrReader → FingerprintFilter → HyphenRestorer → PageMerger → ParagraphBuilder → CleanWriter

输出 clean/document.json（与现有格式兼容） + clean/cleaning_report.json（清洗报告）。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "backend" / "storage" / "tasks"
SENTENCE_ENDINGS = set("。！？；：.!?;:")
MAX_FINGERPRINT_LENGTH = 40
HEADER_FOOTER_TOP_RATIO = 0.12
HEADER_FOOTER_BOTTOM_RATIO = 0.10
REPEATED_PAGE_THRESHOLD = 3
PARAGRAPH_GAP_EM = 1.2


@dataclass
class CleaningStats:
    total_pages: int = 0
    input_ocr_blocks: int = 0
    fingerprinted_removed: int = 0
    fingerprint_reasons: dict[str, int] = field(default_factory=dict)
    hyphen_fixes: int = 0
    hyphen_details: list[dict[str, str]] = field(default_factory=list)
    merged_pairs: int = 0
    merger_details: list[dict[str, Any]] = field(default_factory=list)
    paragraph_breaks: int = 0
    blank_blocks_removed: int = 0
    output_blocks: int = 0


# ---------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------

def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff" or "\uac00" <= char <= "\ud7af"


def is_mostly_cjk(text: str, threshold: float = 0.35) -> bool:
    letters = [ch for ch in text if ch.isalpha() or is_cjk(ch)]
    if not letters:
        return False
    cjk_count = sum(1 for ch in letters if is_cjk(ch))
    return cjk_count / len(letters) >= threshold


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compute_fingerprint(text: str) -> str:
    """提取文本指纹：去标点、去空格、去数字、小写化。"""
    t = text.strip().lower()
    t = re.sub(r"[\s\-—–_｜|·•]+", "", t)
    t = re.sub(r"[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", "", t)
    t = re.sub(r"\d+", "", t)
    return t


def is_page_number(text: str) -> bool:
    t = text.strip()
    if re.fullmatch(r"\d+", t):
        return True
    if re.fullmatch(r"-?\s*\d+\s*-?", t):
        return True
    if re.fullmatch(r"第\s*\d+\s*页", t):
        return True
    if re.fullmatch(r"[IVXLCDM]+", t.upper()):
        return True
    return False


def edges_of_block(block: dict[str, Any], page_height: float, page_width: float) -> dict[str, float]:
    bbox = block.get("bbox", {})
    y1 = safe_float(bbox.get("y1"))
    y2 = safe_float(bbox.get("y2"))
    x1 = safe_float(bbox.get("x1"))
    x2 = safe_float(bbox.get("x2"))
    return {
        "top_ratio": y1 / max(1.0, page_height),
        "bottom_ratio": y2 / max(1.0, page_height),
        "left_ratio": x1 / max(1.0, page_width),
        "right_ratio": x2 / max(1.0, page_width),
    }


# ---------------------------------------------------------------
# 第 1 步：OcrReader —— 读取 OCR 数据
# ---------------------------------------------------------------

def collect_ocr_pages(task_dir: Path) -> list[Path]:
    ocr_dir = task_dir / "ocr"
    if not ocr_dir.exists():
        raise FileNotFoundError(f"OCR 目录不存在: {ocr_dir}")
    pages = sorted(p for p in ocr_dir.glob("page_*.json") if p.name != "summary.json")
    if not pages:
        raise FileNotFoundError(f"OCR 目录中找不到 page_*.json: {ocr_dir}")
    return pages


@dataclass
class PageData:
    page_no: int
    width: float
    height: float
    page_type: str
    layout_type: str
    blocks: list[dict[str, Any]]


def read_all_pages(task_dir: Path) -> tuple[list[PageData], Path]:
    """读取所有 OCR page JSON，合并 layout 元信息。"""
    layout_dir = task_dir / "layout"
    ocr_paths = collect_ocr_pages(task_dir)
    pages: list[PageData] = []

    for ocr_path in ocr_paths:
        ocr_data = load_json(ocr_path)
        page_no = int(ocr_data.get("page_no", 0))

        layout_path = layout_dir / ocr_path.name
        layout_meta: dict[str, Any] = {}
        if layout_path.exists():
            layout_meta = load_json(layout_path)

        width = safe_float(layout_meta.get("width") or ocr_data.get("width", 0))
        height = safe_float(layout_meta.get("height") or ocr_data.get("height", 0))
        page_type = str(layout_meta.get("page_type", "unknown"))
        layout_type = str(layout_meta.get("layout_type", "unknown"))

        blocks = list(ocr_data.get("blocks", []))
        for blk in blocks:
            blk["page_no"] = page_no

        pages.append(PageData(
            page_no=page_no,
            width=width,
            height=height,
            page_type=page_type,
            layout_type=layout_type,
            blocks=blocks,
        ))

    return pages, layout_dir


# ---------------------------------------------------------------
# 第 2 步：FingerprintFilter —— 页眉/页脚/页码指纹去噪
# ---------------------------------------------------------------

def run_fingerprint_filter(pages: list[PageData], stats: CleaningStats) -> None:
    """
    基于指纹 + 位置规则检测并标记噪声 block。

    给每个 block 注入 is_noise: bool 和 noise_reason: str | None。
    """
    all_candidates: list[tuple[int, dict[str, Any], str]] = []  # (page_no, block, fingerprint)

    for page in pages:
        for block in page.blocks:
            text = str(block.get("text", "")).strip()
            if not text:
                block["is_noise"] = True
                block["noise_reason"] = "empty_text"
                continue

            edges = edges_of_block(block, page.height, page.width)
            is_header = edges["top_ratio"] < HEADER_FOOTER_TOP_RATIO
            is_footer = edges["bottom_ratio"] > (1.0 - HEADER_FOOTER_BOTTOM_RATIO)

            # 页码检测 —— 在边缘且格式匹配
            if (is_header or is_footer) and is_page_number(text):
                block["is_noise"] = True
                block["noise_reason"] = "page_number"
                stats.fingerprinted_removed += 1
                stats.fingerprint_reasons["page_number"] = stats.fingerprint_reasons.get("page_number", 0) + 1
                continue

            # 短装饰文本（边缘 + ≤4 字符 + 非 CJK 主导）
            if (is_header or is_footer) and len(text) <= 4 and not is_mostly_cjk(text):
                block["is_noise"] = True
                block["noise_reason"] = "adornment_text"
                stats.fingerprinted_removed += 1
                stats.fingerprint_reasons["adornment_text"] = stats.fingerprint_reasons.get("adornment_text", 0) + 1
                continue

            # 位于版心区域（中间 60%），不作为页眉页脚候选
            in_body_zone = 0.15 <= edges["top_ratio"] <= 0.85
            if in_body_zone:
                block["is_noise"] = False
                block["noise_reason"] = None
                continue

            # 边缘 + 短文本，作为指纹候选
            if (is_header or is_footer) and len(text) <= MAX_FINGERPRINT_LENGTH:
                fp = compute_fingerprint(text)
                if fp:
                    all_candidates.append((page.page_no, block, fp))

    # 跨页指纹聚类
    fp_pages: dict[str, set[int]] = {}
    for page_no, block, fp in all_candidates:
        if fp not in fp_pages:
            fp_pages[fp] = set()
        fp_pages[fp].add(page_no)

    repeated_fps = {fp for fp, pgs in fp_pages.items() if len(pgs) >= REPEATED_PAGE_THRESHOLD}

    for page_no, block, fp in all_candidates:
        if fp in repeated_fps:
            block["is_noise"] = True
            block["noise_reason"] = "repeated_header_footer"
            stats.fingerprinted_removed += 1
            stats.fingerprint_reasons["repeated_header_footer"] = (
                stats.fingerprint_reasons.get("repeated_header_footer", 0) + 1
            )


# ---------------------------------------------------------------
# 第 3 步：HyphenRestorer —— 英文 hyphen 断词恢复
# ---------------------------------------------------------------

def run_hyphen_restorer(pages: list[PageData], stats: CleaningStats) -> None:
    """
    恢复 OCR 中英文单词跨行 hyphen 断词。
    只处理纯字母 hyphen 断词，避免误伤数字或符号场景。
    """
    # 匹配 [a-z][a-z]-\\n[a-z][a-z]，要求 hyphen 前后都是字母
    pattern = re.compile(r"([a-zA-Z]{2,})-\n\s*([a-zA-Z]{2,})")

    for page in pages:
        for block in page.blocks:
            if block.get("is_noise"):
                continue
            text = str(block.get("text", ""))
            if "-\n" not in text:
                continue

            original = text
            text = pattern.sub(lambda m: m.group(1) + m.group(2), text)
            if text != original:
                # 记录前从原始文本提取实际的匹配
                for m in pattern.finditer(original):
                    stats.hyphen_fixes += 1
                    stats.hyphen_details.append({
                        "original": m.group(0),
                        "fixed": m.group(1) + m.group(2),
                        "block_id": block.get("block_id", ""),
                        "page_no": page.page_no,
                    })
                block["text"] = text


# ---------------------------------------------------------------
# 第 4 步：PageMerger —— 跨页段落拼接
# ---------------------------------------------------------------

def run_page_merger(pages: list[PageData], stats: CleaningStats) -> None:
    """
    检测上一页末尾非句号结束的段落，与下一页首个 non-noise body block 合并。
    """
    for i in range(len(pages) - 1):
        cur_page = pages[i]
        next_page = pages[i + 1]

        # 当前页最后一个 non-noise body 类 block
        tail_block = None
        for block in reversed(cur_page.blocks):
            if block.get("is_noise"):
                continue
            role = str(block.get("role", "body"))
            if role in ("body", "unknown"):
                tail_block = block
                break

        if tail_block is None:
            continue

        tail_text = str(tail_block.get("text", "")).strip()
        if not tail_text:
            continue

        # 末尾是句尾标点则不断
        if tail_text and tail_text[-1] in SENTENCE_ENDINGS:
            continue

        # 下一页第一个 non-noise body 类 block
        head_block = None
        for block in next_page.blocks:
            if block.get("is_noise"):
                continue
            role = str(block.get("role", "body"))
            if role in ("body", "unknown"):
                head_block = block
                break

        if head_block is None:
            continue

        head_text = str(head_block.get("text", "")).strip()
        if not head_text:
            continue

        # CJK 文本直接拼接，否则加空格
        if is_mostly_cjk(tail_text[-1:] + head_text[:1]):
            merged = tail_text + head_text
        else:
            merged = tail_text + " " + head_text

        tail_block["text"] = merged
        head_block["text"] = ""
        head_block["is_noise"] = True
        head_block["noise_reason"] = "merged_from_page_merger"

        notes = tail_block.get("notes", [])
        if not isinstance(notes, list):
            notes = []
        notes.append(f"merged_with_page_{next_page.page_no}_head")
        tail_block["notes"] = notes

        stats.merged_pairs += 1
        stats.merger_details.append({
            "from_page": cur_page.page_no,
            "to_page": next_page.page_no,
            "tail_snippet": tail_text[-40:],
            "head_snippet": head_text[:40],
        })


# ---------------------------------------------------------------
# 第 5 步：ParagraphBuilder —— 段落边界重建 + 空白清理
# ---------------------------------------------------------------

def estimate_line_height(blocks: list[dict[str, Any]], page_height: float) -> float:
    heights: list[float] = []
    for blk in blocks:
        role = str(blk.get("role", ""))
        if role not in ("body", "unknown"):
            continue
        bbox = blk.get("bbox", {})
        bh = safe_float(bbox.get("y2", 0)) - safe_float(bbox.get("y1", 0))
        lc = blk.get("line_count", 1)
        if lc and bh > 0:
            heights.append(bh / lc)
    if not heights:
        return page_height * 0.02
    heights.sort()
    return heights[len(heights) // 2] if heights else page_height * 0.02


def run_paragraph_builder(pages: list[PageData], stats: CleaningStats) -> None:
    """
    段落重建：识别段落边界、清理空白、过滤异常字符。
    """
    for page in pages:
        line_height = estimate_line_height(page.blocks, page.height)
        gap_threshold = line_height * PARAGRAPH_GAP_EM

        prev_block = None
        for block in page.blocks:
            if block.get("is_noise"):
                stats.blank_blocks_removed += 1
                continue

            text = str(block.get("text", "")).strip()

            # 清理全角空格和异常字符
            text = text.replace("\u3000", " ").replace("\xa0", " ")
            text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b\u200c\u200d\ufeff]", "", text)
            text = re.sub(r"[□◆◇☆★○●]", "", text)
            text = normalize_text(text)

            if not text:
                block["is_noise"] = True
                block["noise_reason"] = "empty_after_cleaning"
                stats.blank_blocks_removed += 1
                continue

            block["text"] = text

            # 段落边界识别（基于垂直间距）
            if prev_block and block.get("role") in ("body", "unknown"):
                prev_bbox = prev_block.get("bbox", {})
                curr_bbox = block.get("bbox", {})
                gap = safe_float(curr_bbox.get("y1", 0)) - safe_float(prev_bbox.get("y2", 0))
                if gap > gap_threshold and gap > 5:
                    stats.paragraph_breaks += 1
                    block["_paragraph_break"] = True
                else:
                    block["_paragraph_break"] = False
            else:
                block["_paragraph_break"] = False

            prev_block = block


# ---------------------------------------------------------------
# 第 6 步：CleanWriter —— 输出清洗后文档 + 清洗报告
# ---------------------------------------------------------------

def build_clean_document(
    pages: list[PageData], task_dir: Path, stats: CleaningStats,
) -> dict[str, Any]:
    started_at = datetime.now()

    clean_pages: list[dict[str, Any]] = []
    sequence = 1

    for page in pages:
        page_blocks: list[dict[str, Any]] = []
        for block in page.blocks:
            if block.get("is_noise"):
                continue
            text = str(block.get("text", "")).strip()
            if not text:
                continue

            role = str(block.get("role", "body"))
            block_type, level = _classify_block_type(role)
            out = {
                "id": f"c{sequence:05d}",
                "type": block_type,
                "text": text,
                "source_pages": [page.page_no],
                "source_block_ids": [block.get("block_id")],
                "role": role,
                "reading_group": block.get("reading_group", "main"),
                "ocr_confidence": block.get("ocr_confidence"),
                "bbox": block.get("bbox"),
                "order": block.get("order"),
            }
            if level is not None:
                out["level"] = level
            if block.get("_paragraph_break"):
                out["_paragraph_break"] = True
            page_blocks.append(out)
            sequence += 1
            stats.output_blocks += 1

        clean_pages.append({
            "page_no": page.page_no,
            "page_type": page.page_type,
            "layout_type": page.layout_type,
            "blocks": page_blocks,
        })

    # 推断标题
    title = ""
    for p in clean_pages:
        for b in p["blocks"]:
            if b.get("role") == "title":
                title = b["text"]
                break
        if title:
            break
    if not title:
        title = task_dir.name

    return {
        "task_id": task_dir.name,
        "title": title,
        "author": "",
        "language": "zh-CN",
        "summary": "",
        "keywords": [],
        "created_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "stats": {
            "page_count": len(pages),
            "input_ocr_blocks": stats.input_ocr_blocks,
            "output_blocks": stats.output_blocks,
            "paragraph_count": sum(1 for p in clean_pages for b in p["blocks"] if b["type"] == "paragraph"),
            "heading_count": sum(1 for p in clean_pages for b in p["blocks"] if b["type"] == "heading"),
            "caption_count": sum(1 for p in clean_pages for b in p["blocks"] if b["type"] == "caption"),
            "skipped_empty_blocks": stats.blank_blocks_removed,
        },
        "pages": clean_pages,
    }


def _classify_block_type(role: str) -> tuple[str, int | None]:
    if role == "title":
        return "heading", 1
    if role == "subtitle":
        return "heading", 2
    if role == "caption":
        return "caption", None
    if role in ("sidebar", "note"):
        return role, None
    return "paragraph", None


def build_cleaning_report(stats: CleaningStats, task_dir: Path) -> dict[str, Any]:
    return {
        "task_id": task_dir.name,
        "task_dir": project_relative(task_dir),
        "stage": "text_cleaning",
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "stages": {
            "fingerprint_filter": {
                "removed_blocks_count": stats.fingerprinted_removed,
                "removed_reasons": dict(stats.fingerprint_reasons),
            },
            "hyphen_restorer": {
                "fixed_count": stats.hyphen_fixes,
                "details": stats.hyphen_details,
            },
            "page_merger": {
                "merged_pairs": stats.merged_pairs,
                "details": stats.merger_details,
            },
            "paragraph_builder": {
                "paragraph_breaks_detected": stats.paragraph_breaks,
                "blank_blocks_removed": stats.blank_blocks_removed,
            },
        },
    }


def run_cleaning(task_dir: Path) -> dict[str, Any]:
    stats = CleaningStats()
    pages, _ = read_all_pages(task_dir)

    stats.total_pages = len(pages)
    stats.input_ocr_blocks = sum(len(p.blocks) for p in pages)

    # 初始化 is_noise
    for page in pages:
        for block in page.blocks:
            if "is_noise" not in block:
                block["is_noise"] = False
                block["noise_reason"] = None

    run_fingerprint_filter(pages, stats)
    run_hyphen_restorer(pages, stats)
    run_page_merger(pages, stats)
    run_paragraph_builder(pages, stats)

    document = build_clean_document(pages, task_dir, stats)
    report = build_cleaning_report(stats, task_dir)

    clean_dir = task_dir / "clean"
    write_json(clean_dir / "document.json", document)
    write_json(clean_dir / "cleaning_report.json", report)

    print(f"Task ID: {document['task_id']}")
    print(f"总页数: {stats.total_pages}")
    print(f"OCR block 数（清洗前）: {stats.input_ocr_blocks}")
    print(f"输出 block 数（清洗后）: {stats.output_blocks}")
    print(f"指纹去噪移除: {stats.fingerprinted_removed}")
    if stats.fingerprint_reasons:
        print(f"  去噪明细: {dict(stats.fingerprint_reasons)}")
    print(f"Hyphen 修复: {stats.hyphen_fixes}")
    print(f"跨页拼接: {stats.merged_pairs}")
    print(f"段落分界识别: {stats.paragraph_breaks}")
    print(f"空白/异常 block 移除: {stats.blank_blocks_removed}")
    print(f"清洗报告: {project_relative(clean_dir / 'cleaning_report.json')}")
    print(f"文档 JSON: {project_relative(clean_dir / 'document.json')}")

    return document


# ---------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="排版噪声清洗模块")
    parser.add_argument(
        "task",
        help="Task ID（backend/storage/tasks/ 下的目录名）或完整路径",
    )
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
        run_cleaning(task_dir)
    except Exception as exc:
        print(f"清洗失败: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
