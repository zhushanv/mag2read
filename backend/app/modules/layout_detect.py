#!/usr/bin/env python3
"""Run first-layer document layout detection for rendered page images."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "backend" / "storage" / "tasks"
DEFAULT_PADDLEX_CACHE = PROJECT_ROOT / "backend" / "storage" / "paddlex_cache"


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


def import_layout_detection():
    from paddleocr import LayoutDetection

    return LayoutDetection


def normalize_number(value: Any) -> float:
    if hasattr(value, "item"):
        value = value.item()
    return round(float(value), 4)


def normalize_bbox(coordinate: list[Any]) -> dict[str, float]:
    if len(coordinate) != 4:
        raise ValueError(f"Expected bbox coordinate with 4 values, got: {coordinate}")
    x1, y1, x2, y2 = [normalize_number(item) for item in coordinate]
    return {
        "x1": min(x1, x2),
        "y1": min(y1, y2),
        "x2": max(x1, x2),
        "y2": max(y1, y2),
    }


def raw_block_from_box(page_no: int, index: int, box: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_id": f"p{page_no:03d}_raw_{index:04d}",
        "raw_type": str(box.get("label", "unknown")),
        "cls_id": int(box.get("cls_id", -1)),
        "score": normalize_number(box.get("score", 0.0)),
        "bbox": normalize_bbox(list(box.get("coordinate", []))),
    }


def sort_blocks_for_debug(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(blocks, key=lambda block: (block["bbox"]["y1"], block["bbox"]["x1"]))


def draw_overlay(image_path: Path, blocks: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        canvas = image.convert("RGB")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()

        for index, block in enumerate(sort_blocks_for_debug(blocks), start=1):
            bbox = block["bbox"]
            x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
            label = f"{index}:{block['raw_type']} {block['score']:.2f}"
            color = color_for_label(block["raw_type"])
            draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
            text_bbox = draw.textbbox((x1, y1), label, font=font)
            draw.rectangle(text_bbox, fill=color)
            draw.text((x1, y1), label, fill=(255, 255, 255), font=font)

        canvas.save(output_path, format="PNG")


def color_for_label(label: str) -> tuple[int, int, int]:
    colors = {
        "text": (46, 125, 50),
        "paragraph_title": (25, 118, 210),
        "title": (25, 118, 210),
        "image": (230, 81, 0),
        "table": (106, 27, 154),
        "formula": (0, 121, 107),
        "header": (97, 97, 97),
        "footer": (97, 97, 97),
    }
    return colors.get(label, (198, 40, 40))


def page_entry_by_no(metadata: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(page["page_no"]): page for page in metadata.get("pages", [])}


def collect_page_images(task_dir: Path) -> list[Path]:
    pages_dir = task_dir / "pages"
    if not pages_dir.exists():
        raise FileNotFoundError(f"Pages directory does not exist: {pages_dir}")
    pages = sorted(pages_dir.glob("page_*.png"))
    if not pages:
        raise FileNotFoundError(f"No page PNG files found in: {pages_dir}")
    return pages


def parse_page_no(image_path: Path) -> int:
    stem = image_path.stem
    try:
        return int(stem.split("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Page image name must look like page_001.png: {image_path}") from exc


def analyze_task_layout(
    task_dir: Path,
    cache_dir: Path,
    threshold: float | None,
    draw_debug: bool,
) -> dict[str, Any]:
    metadata_path = task_dir / "metadata.json"
    metadata = load_json(metadata_path) if metadata_path.exists() else {}
    page_meta = page_entry_by_no(metadata)
    page_images = collect_page_images(task_dir)

    configure_paddlex_cache(cache_dir)
    LayoutDetection = import_layout_detection()
    detector_kwargs: dict[str, Any] = {}
    if threshold is not None:
        detector_kwargs["threshold"] = threshold
    detector = LayoutDetection(**detector_kwargs)

    started_at = datetime.now()
    page_summaries: list[dict[str, Any]] = []
    total_blocks = 0

    for image_path in page_images:
        page_no = parse_page_no(image_path)
        detect_start = time.perf_counter()
        results = detector.predict(str(image_path))
        detect_seconds = round(time.perf_counter() - detect_start, 4)
        if not results:
            raw_boxes: list[dict[str, Any]] = []
        else:
            raw_boxes = list(results[0].get("boxes", []))

        blocks = [
            raw_block_from_box(page_no=page_no, index=index, box=box)
            for index, box in enumerate(raw_boxes, start=1)
        ]
        total_blocks += len(blocks)

        image_info = page_meta.get(page_no, {})
        page_data = {
            "task_id": task_dir.name,
            "page_no": page_no,
            "image_path": project_relative(image_path),
            "width": image_info.get("width"),
            "height": image_info.get("height"),
            "detector": {
                "name": "PaddleOCR LayoutDetection",
                "threshold": threshold,
                "detect_seconds": detect_seconds,
            },
            "raw_blocks": blocks,
        }

        layout_raw_path = task_dir / "layout_raw" / f"page_{page_no:03d}.json"
        write_json(layout_raw_path, page_data)

        overlay_path = None
        if draw_debug:
            overlay_path = task_dir / "debug" / f"page_{page_no:03d}_layout_overlay.png"
            draw_overlay(image_path, blocks, overlay_path)

        page_summaries.append(
            {
                "page_no": page_no,
                "image_path": project_relative(image_path),
                "layout_raw_path": project_relative(layout_raw_path),
                "debug_overlay_path": project_relative(overlay_path) if overlay_path else None,
                "raw_block_count": len(blocks),
                "detect_seconds": detect_seconds,
                "labels": summarize_labels(blocks),
            }
        )

    summary = {
        "task_id": task_dir.name,
        "task_dir": project_relative(task_dir),
        "stage": "layout_raw",
        "detector": "PaddleOCR LayoutDetection",
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "page_count": len(page_images),
        "total_raw_blocks": total_blocks,
        "pages": page_summaries,
    }
    write_json(task_dir / "layout_raw" / "summary.json", summary)
    return summary


def summarize_labels(blocks: list[dict[str, Any]]) -> dict[str, int]:
    labels: dict[str, int] = {}
    for block in blocks:
        label = str(block.get("raw_type", "unknown"))
        labels[label] = labels.get(label, 0) + 1
    return labels


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run first-layer PP-DocLayout/LayoutDetection analysis for rendered task pages."
    )
    parser.add_argument(
        "task",
        help="Task ID under backend/storage/tasks, or an explicit task directory path.",
    )
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
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Optional layout detection threshold passed to PaddleOCR LayoutDetection.",
    )
    parser.add_argument(
        "--no-debug-overlay",
        action="store_true",
        help="Do not draw layout overlay PNG files.",
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

    storage_root = Path(args.storage_root).expanduser().resolve()
    task_dir = resolve_task_dir(args.task, storage_root)
    cache_dir = Path(args.paddlex_cache).expanduser().resolve()

    try:
        summary = analyze_task_layout(
            task_dir=task_dir,
            cache_dir=cache_dir,
            threshold=args.threshold,
            draw_debug=not args.no_debug_overlay,
        )
    except Exception as exc:
        print(f"Layout analysis failed: {exc}")
        return 1

    print(f"Analyzed {summary['page_count']} page(s).")
    print(f"Task ID: {summary['task_id']}")
    print(f"Raw blocks: {summary['total_raw_blocks']}")
    print(f"Summary: {summary['task_dir']}/layout_raw/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
