#!/usr/bin/env python3
"""Run OCR on text-like layout blocks and write block-aligned OCR JSON files."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "backend" / "storage" / "tasks"
DEFAULT_PADDLEX_CACHE = PROJECT_ROOT / "backend" / "storage" / "paddlex_cache"

OCR_ROLES = {"title", "subtitle", "body", "caption", "sidebar", "note"}
SKIP_ROLES = {"figure", "table", "formula", "header", "footer", "page_number", "adornment"}
SLOW_BLOCK_SECONDS = 2.0


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def configure_paddlex_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_dir)


def import_paddle_ocr():
    from paddleocr import PaddleOCR

    return PaddleOCR


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round4(value: float) -> float:
    return round(float(value), 4)


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def crop_box_from_bbox(bbox: dict[str, Any], image_width: int, image_height: int, padding: int) -> tuple[int, int, int, int]:
    x1 = clamp(int(safe_float(bbox.get("x1"))) - padding, 0, image_width)
    y1 = clamp(int(safe_float(bbox.get("y1"))) - padding, 0, image_height)
    x2 = clamp(int(safe_float(bbox.get("x2"))) + padding, 0, image_width)
    y2 = clamp(int(safe_float(bbox.get("y2"))) + padding, 0, image_height)
    if x2 <= x1:
        x2 = min(image_width, x1 + 1)
    if y2 <= y1:
        y2 = min(image_height, y1 + 1)
    return x1, y1, x2, y2


def should_ocr_block(block: dict[str, Any], include_unknown: bool) -> tuple[bool, str | None]:
    if block.get("is_noise"):
        return False, "noise_block"
    role = str(block.get("role", "unknown"))
    if role in OCR_ROLES:
        return True, None
    if include_unknown and role == "unknown":
        return True, None
    if role in SKIP_ROLES:
        return False, f"skip_role:{role}"
    return False, f"unsupported_role:{role}"


def result_get(result: Any, key: str, default: Any = None) -> Any:
    if hasattr(result, "get"):
        return result.get(key, default)
    try:
        return result[key]
    except Exception:
        return default


def result_list(result: Any, key: str) -> list[Any]:
    value = result_get(result, key, [])
    if value is None:
        return []
    return list(value)


def normalize_polygon(poly: Any, offset_x: int, offset_y: int) -> list[list[float]]:
    points: list[list[float]] = []
    if poly is None:
        return points
    for point in poly:
        x, y = point
        points.append([round4(safe_float(x) + offset_x), round4(safe_float(y) + offset_y)])
    return points


def normalize_box(box: Any, offset_x: int, offset_y: int) -> dict[str, float]:
    if box is None or len(box) < 4:
        return {"x1": 0.0, "y1": 0.0, "x2": 0.0, "y2": 0.0}
    return {
        "x1": round4(safe_float(box[0]) + offset_x),
        "y1": round4(safe_float(box[1]) + offset_y),
        "x2": round4(safe_float(box[2]) + offset_x),
        "y2": round4(safe_float(box[3]) + offset_y),
    }


def run_ocr_on_crop(ocr: Any, crop_path: Path, offset_x: int, offset_y: int) -> tuple[list[dict[str, Any]], str, float | None, float]:
    predict_started = time.perf_counter()
    results = ocr.predict(str(crop_path))
    predict_seconds = round4(time.perf_counter() - predict_started)
    if not results:
        return [], "", None, predict_seconds

    result = results[0]
    texts = result_list(result, "rec_texts")
    scores = result_list(result, "rec_scores")
    polys = result_list(result, "rec_polys")
    boxes = result_list(result, "rec_boxes")

    lines: list[dict[str, Any]] = []
    for index, text in enumerate(texts):
        score = safe_float(scores[index]) if index < len(scores) else 0.0
        poly = polys[index] if index < len(polys) else None
        box = boxes[index] if index < len(boxes) else None
        lines.append(
            {
                "line_no": index + 1,
                "text": str(text),
                "confidence": round4(score),
                "bbox": normalize_box(box, offset_x, offset_y),
                "polygon": normalize_polygon(poly, offset_x, offset_y),
            }
        )

    merged_text = "\n".join(line["text"] for line in lines)
    avg_confidence = None
    if lines:
        avg_confidence = round4(sum(line["confidence"] for line in lines) / len(lines))
    return lines, merged_text, avg_confidence, predict_seconds


def collect_layout_pages(task_dir: Path) -> list[Path]:
    layout_dir = task_dir / "layout"
    if not layout_dir.exists():
        raise FileNotFoundError(f"layout directory does not exist: {layout_dir}")
    pages = sorted(path for path in layout_dir.glob("page_*.json") if path.name != "summary.json")
    if not pages:
        raise FileNotFoundError(f"No layout page JSON files found in: {layout_dir}")
    return pages


def init_ocr(cache_dir: Path, use_textline_orientation: bool) -> Any:
    configure_paddlex_cache(cache_dir)
    PaddleOCR = import_paddle_ocr()
    return PaddleOCR(
        lang="ch",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=use_textline_orientation,
    )


def init_ocr_with_timing(cache_dir: Path, use_textline_orientation: bool) -> tuple[Any, dict[str, Any]]:
    started = time.perf_counter()
    cache_dir.mkdir(parents=True, exist_ok=True)
    before_models = sorted(str(path.relative_to(cache_dir)) for path in cache_dir.glob("official_models/*"))
    ocr = init_ocr(cache_dir, use_textline_orientation=use_textline_orientation)
    after_models = sorted(str(path.relative_to(cache_dir)) for path in cache_dir.glob("official_models/*"))
    timing = {
        "ocr_model_init_seconds": round4(time.perf_counter() - started),
        "paddlex_cache_dir": project_relative(cache_dir),
        "models_before_count": len(before_models),
        "models_after_count": len(after_models),
        "models_added": [model for model in after_models if model not in set(before_models)],
        "use_textline_orientation": use_textline_orientation,
    }
    return ocr, timing


def ocr_page(
    page_layout: dict[str, Any],
    task_dir: Path,
    ocr: Any,
    crop_dir: Path,
    padding: int,
    include_unknown: bool,
    save_crops: bool,
) -> dict[str, Any]:
    page_no = int(page_layout["page_no"])
    image_path = (PROJECT_ROOT / page_layout["image_path"]).resolve()
    if not image_path.exists():
        image_path = (task_dir / page_layout["image_path"]).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Page image does not exist: {page_layout['image_path']}")

    blocks_out: list[dict[str, Any]] = []
    skipped_blocks: list[dict[str, Any]] = []
    block_timings: list[dict[str, Any]] = []
    started = time.perf_counter()

    with Image.open(image_path) as image:
        image = image.convert("RGB")
        image_width, image_height = image.size

        for block in sorted(page_layout.get("blocks", []), key=lambda item: (item.get("order") is None, item.get("order") or 0, item.get("block_id", ""))):
            should_ocr, skip_reason = should_ocr_block(block, include_unknown=include_unknown)
            if not should_ocr:
                skipped_blocks.append(
                    {
                        "block_id": block.get("block_id"),
                        "role": block.get("role"),
                        "reading_group": block.get("reading_group"),
                        "reason": skip_reason,
                    }
                )
                continue

            block_started = time.perf_counter()
            crop_started = time.perf_counter()
            crop_box = crop_box_from_bbox(block["bbox"], image_width, image_height, padding)
            crop = image.crop(crop_box)
            crop_seconds = round4(time.perf_counter() - crop_started)

            save_started = time.perf_counter()
            crop_path = crop_dir / f"page_{page_no:03d}_{block['block_id']}.png"
            crop_path.parent.mkdir(parents=True, exist_ok=True)
            crop.save(crop_path, format="PNG")
            crop_save_seconds = round4(time.perf_counter() - save_started)

            lines, text, confidence, predict_seconds = run_ocr_on_crop(ocr, crop_path, crop_box[0], crop_box[1])

            cleanup_started = time.perf_counter()
            if not save_crops:
                crop_path.unlink(missing_ok=True)
            cleanup_seconds = round4(time.perf_counter() - cleanup_started)
            block_seconds = round4(time.perf_counter() - block_started)

            timing = {
                "block_id": block["block_id"],
                "role": block["role"],
                "order": block.get("order"),
                "line_count": len(lines),
                "text_length": len(text),
                "crop_width": crop_box[2] - crop_box[0],
                "crop_height": crop_box[3] - crop_box[1],
                "crop_seconds": crop_seconds,
                "crop_save_seconds": crop_save_seconds,
                "predict_seconds": predict_seconds,
                "cleanup_seconds": cleanup_seconds,
                "total_seconds": block_seconds,
                "is_slow": block_seconds >= SLOW_BLOCK_SECONDS,
            }
            block_timings.append(timing)

            blocks_out.append(
                {
                    "block_id": block["block_id"],
                    "page_no": page_no,
                    "role": block["role"],
                    "raw_type": block.get("raw_type"),
                    "text": text,
                    "ocr_confidence": confidence,
                    "bbox": block["bbox"],
                    "column": block.get("column"),
                    "order": block.get("order"),
                    "reading_group": block.get("reading_group"),
                    "layout_confidence": block.get("confidence"),
                    "line_count": len(lines),
                    "lines": lines,
                    "crop_path": project_relative(crop_path) if save_crops else None,
                    "timing": timing,
                }
            )

    recognized_blocks = [block for block in blocks_out if block["text"]]
    confidences = [block["ocr_confidence"] for block in recognized_blocks if block["ocr_confidence"] is not None]
    page_confidence = round4(sum(confidences) / len(confidences)) if confidences else None
    total_predict_seconds = round4(sum(item["predict_seconds"] for item in block_timings))
    total_block_seconds = round4(sum(item["total_seconds"] for item in block_timings))
    slow_blocks = sorted(
        [item for item in block_timings if item["is_slow"]],
        key=lambda item: item["total_seconds"],
        reverse=True,
    )
    page_ocr_seconds = round4(time.perf_counter() - started)
    return {
        "task_id": page_layout["task_id"],
        "page_no": page_no,
        "image_path": page_layout["image_path"],
        "page_type": page_layout.get("page_type"),
        "layout_type": page_layout.get("layout_type"),
        "ocr_seconds": page_ocr_seconds,
        "ocr_block_count": len(blocks_out),
        "recognized_block_count": len(recognized_blocks),
        "skipped_block_count": len(skipped_blocks),
        "line_count": sum(block["line_count"] for block in blocks_out),
        "avg_confidence": page_confidence,
        "timing": {
            "page_ocr_seconds": page_ocr_seconds,
            "total_block_seconds": total_block_seconds,
            "total_predict_seconds": total_predict_seconds,
            "avg_block_seconds": round4(total_block_seconds / len(block_timings)) if block_timings else 0.0,
            "avg_predict_seconds": round4(total_predict_seconds / len(block_timings)) if block_timings else 0.0,
            "max_block_seconds": max((item["total_seconds"] for item in block_timings), default=0.0),
            "max_predict_seconds": max((item["predict_seconds"] for item in block_timings), default=0.0),
            "slow_block_threshold_seconds": SLOW_BLOCK_SECONDS,
            "slow_block_count": len(slow_blocks),
            "slow_blocks": slow_blocks[:10],
        },
        "blocks": blocks_out,
        "skipped_blocks": skipped_blocks,
    }


def summarize_ocr_pages(pages: list[dict[str, Any]], task_dir: Path, started_at: datetime, init_timing: dict[str, Any]) -> dict[str, Any]:
    total_blocks = sum(page["ocr_block_count"] for page in pages)
    recognized_blocks = sum(page["recognized_block_count"] for page in pages)
    skipped_blocks = sum(page["skipped_block_count"] for page in pages)
    total_lines = sum(page["line_count"] for page in pages)
    confidences = [page["avg_confidence"] for page in pages if page["avg_confidence"] is not None]
    avg_confidence = round4(sum(confidences) / len(confidences)) if confidences else None
    low_confidence_blocks = 0
    empty_blocks = 0
    role_counts: dict[str, int] = {}
    page_timings = [page.get("timing", {}) for page in pages]
    total_page_ocr_seconds = round4(sum(safe_float(item.get("page_ocr_seconds")) for item in page_timings))
    total_predict_seconds = round4(sum(safe_float(item.get("total_predict_seconds")) for item in page_timings))
    total_block_seconds = round4(sum(safe_float(item.get("total_block_seconds")) for item in page_timings))
    slow_blocks_all: list[dict[str, Any]] = []

    for page in pages:
        for slow_block in page.get("timing", {}).get("slow_blocks", []):
            item = dict(slow_block)
            item["page_no"] = page["page_no"]
            slow_blocks_all.append(item)
        for block in page["blocks"]:
            role = str(block["role"])
            role_counts[role] = role_counts.get(role, 0) + 1
            if not block["text"]:
                empty_blocks += 1
            if block["ocr_confidence"] is not None and block["ocr_confidence"] < 0.80:
                low_confidence_blocks += 1

    slow_blocks_all.sort(key=lambda item: item["total_seconds"], reverse=True)
    total_ocr_seconds = round4(safe_float(init_timing.get("ocr_model_init_seconds")) + total_page_ocr_seconds)

    return {
        "task_id": task_dir.name,
        "task_dir": project_relative(task_dir),
        "stage": "ocr",
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "page_count": len(pages),
        "ocr_block_count": total_blocks,
        "recognized_block_count": recognized_blocks,
        "empty_block_count": empty_blocks,
        "skipped_block_count": skipped_blocks,
        "line_count": total_lines,
        "avg_confidence": avg_confidence,
        "low_confidence_block_count": low_confidence_blocks,
        "role_counts": role_counts,
        "timing": {
            **init_timing,
            "total_ocr_seconds": total_ocr_seconds,
            "total_page_ocr_seconds": total_page_ocr_seconds,
            "total_block_seconds": total_block_seconds,
            "total_predict_seconds": total_predict_seconds,
            "avg_page_ocr_seconds": round4(total_page_ocr_seconds / len(pages)) if pages else 0.0,
            "avg_block_seconds": round4(total_block_seconds / total_blocks) if total_blocks else 0.0,
            "avg_predict_seconds": round4(total_predict_seconds / total_blocks) if total_blocks else 0.0,
            "max_page_ocr_seconds": max((safe_float(item.get("page_ocr_seconds")) for item in page_timings), default=0.0),
            "max_block_seconds": max((safe_float(item.get("max_block_seconds")) for item in page_timings), default=0.0),
            "max_predict_seconds": max((safe_float(item.get("max_predict_seconds")) for item in page_timings), default=0.0),
            "slow_block_threshold_seconds": SLOW_BLOCK_SECONDS,
            "slow_block_count": len(slow_blocks_all),
            "slow_blocks": slow_blocks_all[:20],
        },
        "pages": [
            {
                "page_no": page["page_no"],
                "ocr_path": project_relative(task_dir / "ocr" / f"page_{int(page['page_no']):03d}.json"),
                "ocr_block_count": page["ocr_block_count"],
                "recognized_block_count": page["recognized_block_count"],
                "skipped_block_count": page["skipped_block_count"],
                "line_count": page["line_count"],
                "avg_confidence": page["avg_confidence"],
                "timing": page.get("timing", {}),
            }
            for page in pages
        ],
    }


def run_task_ocr(
    task_dir: Path,
    cache_dir: Path,
    padding: int,
    include_unknown: bool,
    save_crops: bool,
    use_textline_orientation: bool,
) -> dict[str, Any]:
    started_at = datetime.now()
    print(f"[ocr] initializing PaddleOCR, cache_dir={cache_dir}")
    ocr, init_timing = init_ocr_with_timing(cache_dir, use_textline_orientation=use_textline_orientation)
    print(f"[ocr] PaddleOCR initialized in {init_timing['ocr_model_init_seconds']}s")
    crop_dir = task_dir / "ocr_crops"
    page_outputs: list[dict[str, Any]] = []

    for layout_path in collect_layout_pages(task_dir):
        page_layout = load_json(layout_path)
        print(f"[ocr] page {page_layout.get('page_no')} started: {layout_path.name}")
        page_output = ocr_page(
            page_layout=page_layout,
            task_dir=task_dir,
            ocr=ocr,
            crop_dir=crop_dir,
            padding=padding,
            include_unknown=include_unknown,
            save_crops=save_crops,
        )
        print(
            "[ocr] page {page_no} finished: blocks={blocks}, recognized={recognized}, "
            "page_seconds={seconds}, predict_seconds={predict}, slow_blocks={slow}".format(
                page_no=page_output["page_no"],
                blocks=page_output["ocr_block_count"],
                recognized=page_output["recognized_block_count"],
                seconds=page_output["timing"]["page_ocr_seconds"],
                predict=page_output["timing"]["total_predict_seconds"],
                slow=page_output["timing"]["slow_block_count"],
            )
        )
        page_outputs.append(page_output)
        write_json(task_dir / "ocr" / f"page_{int(page_output['page_no']):03d}.json", page_output)

    if not save_crops and crop_dir.exists():
        # Directory may be empty after deleting crops; keep output tree tidy.
        try:
            crop_dir.rmdir()
        except OSError:
            pass

    summary = summarize_ocr_pages(page_outputs, task_dir, started_at, init_timing=init_timing)
    write_json(task_dir / "ocr" / "summary.json", summary)
    print(
        "[ocr] task finished: total={total}s, init={init}s, page_total={pages}s, predict_total={predict}s, slow_blocks={slow}".format(
            total=summary["timing"]["total_ocr_seconds"],
            init=summary["timing"]["ocr_model_init_seconds"],
            pages=summary["timing"]["total_page_ocr_seconds"],
            predict=summary["timing"]["total_predict_seconds"],
            slow=summary["timing"]["slow_block_count"],
        )
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OCR on text-like blocks from refined layout JSON files.")
    parser.add_argument("task", help="Task ID under backend/storage/tasks, or an explicit task directory path.")
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
        help=f"Directory that stores task folders. Default: {DEFAULT_STORAGE_ROOT}",
    )
    parser.add_argument(
        "--paddlex-cache",
        default=str(DEFAULT_PADDLEX_CACHE),
        help=f"PaddleX model cache directory. Default: {DEFAULT_PADDLEX_CACHE}",
    )
    parser.add_argument("--padding", type=int, default=4, help="Pixel padding added around each OCR crop.")
    parser.add_argument("--include-unknown", action="store_true", help="OCR unknown layout blocks as well.")
    parser.add_argument("--save-crops", action="store_true", help="Keep OCR crop images for debugging.")
    parser.add_argument(
        "--use-textline-orientation",
        action="store_true",
        help="Enable PaddleOCR textline orientation model. This may require an extra model download.",
    )
    return parser


def resolve_task_dir(task: str, storage_root: Path) -> Path:
    task_path = Path(task).expanduser()
    if task_path.exists():
        return task_path.resolve()
    return (storage_root / task).resolve()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    task_dir = resolve_task_dir(args.task, Path(args.storage_root).expanduser().resolve())

    try:
        summary = run_task_ocr(
            task_dir=task_dir,
            cache_dir=Path(args.paddlex_cache).expanduser().resolve(),
            padding=args.padding,
            include_unknown=args.include_unknown,
            save_crops=args.save_crops,
            use_textline_orientation=args.use_textline_orientation,
        )
    except Exception as exc:
        print(f"OCR failed: {exc}")
        return 1

    print(f"OCR processed {summary['page_count']} page(s).")
    print(f"Task ID: {summary['task_id']}")
    print(f"OCR blocks: {summary['ocr_block_count']}")
    print(f"Recognized blocks: {summary['recognized_block_count']}")
    print(f"Lines: {summary['line_count']}")
    print(f"Average confidence: {summary['avg_confidence']}")
    print(f"Summary: {summary['task_dir']}/ocr/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
