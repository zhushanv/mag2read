#!/usr/bin/env python3
"""Build stable media image assets for graphical layout blocks."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MEDIA_ROLES = {"figure", "image", "table", "formula"}


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


def collect_layout_pages(task_dir: Path) -> list[Path]:
    layout_dir = task_dir / "layout"
    if not layout_dir.exists():
        return []
    return sorted(path for path in layout_dir.glob("page_*.json") if path.name != "summary.json")


def resolve_page_image(task_dir: Path, page_data: dict[str, Any], page_no: int) -> Path | None:
    candidates: list[Path] = []
    image_path = str(page_data.get("image_path") or "").strip()
    if image_path:
        raw_path = Path(image_path)
        candidates.append(raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path)
        candidates.append(task_dir / raw_path)
    candidates.append(task_dir / "pages" / f"page_{page_no:03d}.png")

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def scale_bbox_to_image(
    bbox: dict[str, Any],
    layout_width: float,
    layout_height: float,
    image_width: int,
    image_height: int,
    padding: int,
) -> tuple[int, int, int, int] | None:
    x1 = safe_float(bbox.get("x1"))
    y1 = safe_float(bbox.get("y1"))
    x2 = safe_float(bbox.get("x2"))
    y2 = safe_float(bbox.get("y2"))
    if x2 <= x1 or y2 <= y1:
        return None

    scale_x = image_width / layout_width if layout_width > 0 else 1.0
    scale_y = image_height / layout_height if layout_height > 0 else 1.0

    left = int(max(0, min(image_width - 1, x1 * scale_x - padding)))
    upper = int(max(0, min(image_height - 1, y1 * scale_y - padding)))
    right = int(max(left + 1, min(image_width, x2 * scale_x + padding)))
    lower = int(max(upper + 1, min(image_height, y2 * scale_y + padding)))
    if right <= left or lower <= upper:
        return None
    return left, upper, right, lower


def media_filename(page_no: int, block_id: str, role: str) -> str:
    safe_block_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in block_id)
    safe_role = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in role)
    return f"page_{page_no:03d}_{safe_block_id}_{safe_role}.png"


def build_media_assets(task_dir: Path, padding: int = 6) -> dict[str, Any]:
    started_at = datetime.now()
    media_dir = task_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    media_items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for layout_path in collect_layout_pages(task_dir):
        page_data = load_json(layout_path)
        page_no = int(page_data.get("page_no") or layout_path.stem.split("_", 1)[1])
        page_image = resolve_page_image(task_dir, page_data, page_no)
        if page_image is None:
            skipped.append({"page_no": page_no, "reason": "page_image_missing"})
            continue

        with Image.open(page_image) as image:
            image = image.convert("RGB")
            image_width, image_height = image.size
            layout_width = safe_float(page_data.get("width"), image_width)
            layout_height = safe_float(page_data.get("height"), image_height)

            for block in page_data.get("blocks", []):
                role = str(block.get("role") or block.get("type") or "").lower()
                if role not in MEDIA_ROLES:
                    continue
                block_id = str(block.get("block_id") or block.get("id") or f"p{page_no:03d}_media_{len(media_items) + 1:04d}")
                crop_box = scale_bbox_to_image(
                    dict(block.get("bbox") or {}),
                    layout_width=layout_width,
                    layout_height=layout_height,
                    image_width=image_width,
                    image_height=image_height,
                    padding=padding,
                )
                if crop_box is None:
                    skipped.append({"page_no": page_no, "block_id": block_id, "role": role, "reason": "invalid_bbox"})
                    continue

                crop = image.crop(crop_box)
                output_path = media_dir / media_filename(page_no, block_id, role)
                crop.save(output_path, format="PNG")
                media_items.append(
                    {
                        "block_id": block_id,
                        "page_no": page_no,
                        "role": role,
                        "media_path": project_relative(output_path),
                        "source_image_path": project_relative(page_image),
                        "bbox": block.get("bbox"),
                        "crop_box": {
                            "x1": crop_box[0],
                            "y1": crop_box[1],
                            "x2": crop_box[2],
                            "y2": crop_box[3],
                        },
                        "width": crop.width,
                        "height": crop.height,
                    }
                )

    summary = {
        "task_id": task_dir.name,
        "task_dir": project_relative(task_dir),
        "stage": "media",
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "media_count": len(media_items),
        "skipped_count": len(skipped),
        "items": media_items,
        "skipped": skipped,
    }
    write_json(media_dir / "summary.json", summary)
    return summary
