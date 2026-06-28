#!/usr/bin/env python3
"""Refine raw layout detection results into normalized layout JSON files."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "backend" / "storage" / "tasks"


RAW_TYPE_MAPPING: dict[str, tuple[str, str]] = {
    "doc_title": ("title", "main"),
    "title": ("title", "main"),
    "paragraph_title": ("subtitle", "main"),
    "figure_title": ("caption", "caption"),
    "table_title": ("caption", "caption"),
    "text": ("body", "main"),
    "plain text": ("body", "main"),
    "image": ("figure", "visual"),
    "figure": ("figure", "visual"),
    "table": ("table", "visual"),
    "formula": ("formula", "visual"),
    "header": ("header", "noise"),
    "footer": ("footer", "noise"),
    "reference": ("body", "main"),
}


VISUAL_ROLES = {"figure", "table", "formula"}
TEXTUAL_ROLES = {"title", "subtitle", "body", "caption", "sidebar"}
NOISE_ROLES = {"header", "footer", "page_number", "adornment"}


@dataclass
class Metrics:
    width: float
    height: float
    area: float
    area_ratio: float
    center_x: float
    center_y: float
    top_ratio: float
    bottom_ratio: float
    left_ratio: float
    right_ratio: float


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


def round4(value: float) -> float:
    return round(float(value), 4)


def compute_metrics(bbox: dict[str, Any], page_width: float, page_height: float) -> Metrics:
    x1 = safe_float(bbox.get("x1"))
    y1 = safe_float(bbox.get("y1"))
    x2 = safe_float(bbox.get("x2"))
    y2 = safe_float(bbox.get("y2"))
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    area = width * height
    page_area = max(1.0, page_width * page_height)
    return Metrics(
        width=width,
        height=height,
        area=area,
        area_ratio=area / page_area,
        center_x=(x1 + x2) / 2,
        center_y=(y1 + y2) / 2,
        top_ratio=y1 / max(1.0, page_height),
        bottom_ratio=y2 / max(1.0, page_height),
        left_ratio=x1 / max(1.0, page_width),
        right_ratio=x2 / max(1.0, page_width),
    )


def base_role(raw_type: str) -> tuple[str, str, float, list[str]]:
    normalized = raw_type.strip().lower()
    role, reading_group = RAW_TYPE_MAPPING.get(normalized, ("unknown", "unknown"))
    rule_confidence = 0.85 if role != "unknown" else 0.40
    notes = [] if role != "unknown" else [f"unmapped_raw_type:{raw_type}"]
    return role, reading_group, rule_confidence, notes


def is_handwriting_page(raw_blocks: list[dict[str, Any]]) -> bool:
    total = len(raw_blocks)
    if total == 0:
        return False
    counts = count_raw_types(raw_blocks)
    formula_count = counts.get("formula", 0)
    table_count = counts.get("table", 0)
    image_count = counts.get("image", 0) + counts.get("figure", 0)
    return formula_count / total >= 0.5 and table_count == 0 and image_count <= 1


def count_raw_types(raw_blocks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for block in raw_blocks:
        raw_type = str(block.get("raw_type", "unknown")).strip().lower()
        counts[raw_type] = counts.get(raw_type, 0) + 1
    return counts


def create_initial_blocks(page_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_blocks = page_data.get("raw_blocks", [])
    page_width = safe_float(page_data.get("width"))
    page_height = safe_float(page_data.get("height"))
    handwriting = is_handwriting_page(raw_blocks)
    blocks: list[dict[str, Any]] = []

    for index, raw_block in enumerate(raw_blocks, start=1):
        raw_type = str(raw_block.get("raw_type", "unknown"))
        bbox = dict(raw_block.get("bbox", {}))
        metrics = compute_metrics(bbox, page_width, page_height)
        role, reading_group, rule_confidence, notes = base_role(raw_type)
        source = "rule_mapped"

        if handwriting and raw_type.strip().lower() == "formula":
            role = "body"
            reading_group = "main"
            rule_confidence = 0.75
            source = "rule_corrected"
            notes.append("formula_reclassified_as_handwriting_body")

        role, reading_group, rule_confidence, source, notes = apply_position_rules(
            role=role,
            reading_group=reading_group,
            rule_confidence=rule_confidence,
            source=source,
            notes=notes,
            raw_type=raw_type,
            metrics=metrics,
            page_width=page_width,
            page_height=page_height,
        )

        detector_confidence = round4(safe_float(raw_block.get("score")))
        final_confidence = round4((detector_confidence + rule_confidence) / 2)
        block = {
            "block_id": f"p{int(page_data.get('page_no', 0)):03d}_b{index:04d}",
            "source": source,
            "raw_id": raw_block.get("raw_id"),
            "raw_type": raw_type,
            "role": role,
            "bbox": {
                "x1": round4(safe_float(bbox.get("x1"))),
                "y1": round4(safe_float(bbox.get("y1"))),
                "x2": round4(safe_float(bbox.get("x2"))),
                "y2": round4(safe_float(bbox.get("y2"))),
            },
            "confidence": {
                "detector": detector_confidence,
                "rule": round4(rule_confidence),
                "final": final_confidence,
            },
            "column": None,
            "order": None,
            "reading_group": reading_group,
            "is_noise": reading_group == "noise" or role in NOISE_ROLES,
            "notes": notes,
        }
        blocks.append(block)

    promote_first_subtitle_if_needed(blocks, page_width, page_height)
    return blocks


def apply_position_rules(
    role: str,
    reading_group: str,
    rule_confidence: float,
    source: str,
    notes: list[str],
    raw_type: str,
    metrics: Metrics,
    page_width: float,
    page_height: float,
) -> tuple[str, str, float, str, list[str]]:
    raw_type_normalized = raw_type.strip().lower()
    is_small_height = metrics.height / max(1.0, page_height) <= 0.05
    is_large_title = role == "title" and metrics.width / max(1.0, page_width) >= 0.60

    if metrics.top_ratio <= 0.08 and is_small_height and not is_large_title:
        if role not in {"figure", "table"}:
            if role != "header":
                notes.append("position_corrected_to_header")
            return "header", "noise", 0.80, "rule_corrected", notes

    if metrics.bottom_ratio >= 0.94 and is_small_height and role not in {"figure", "table"}:
        if role != "footer":
            notes.append("position_corrected_to_footer")
        return "footer", "noise", 0.80, "rule_corrected", notes

    if role in {"title", "subtitle"} and metrics.top_ratio >= 0.86 and metrics.height / max(1.0, page_height) <= 0.04:
        notes.append("bottom_ui_title_reclassified_as_adornment")
        return "adornment", "noise", 0.70, "rule_corrected", notes

    if raw_type_normalized == "doc_title":
        return "title", "main", 0.85, source, notes

    return role, reading_group, rule_confidence, source, notes


def promote_first_subtitle_if_needed(blocks: list[dict[str, Any]], page_width: float, page_height: float) -> None:
    if any(block["role"] == "title" for block in blocks):
        return
    candidates = [
        block
        for block in blocks
        if block["role"] == "subtitle"
        and not block["is_noise"]
        and safe_float(block["bbox"]["y1"]) / max(1.0, page_height) <= 0.60
    ]
    if not candidates:
        return
    candidates.sort(key=lambda block: (safe_float(block["bbox"]["y1"]), safe_float(block["bbox"]["x1"])))
    block = candidates[0]
    block["role"] = "title"
    block["source"] = "rule_corrected"
    block["confidence"]["rule"] = 0.70
    block["confidence"]["final"] = round4((block["confidence"]["detector"] + 0.70) / 2)
    block["notes"].append("first_subtitle_promoted_to_title")


def compute_role_counts(blocks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for block in blocks:
        role = str(block.get("role", "unknown"))
        counts[role] = counts.get(role, 0) + 1
    return counts


def compute_area_ratio(blocks: list[dict[str, Any]], roles: set[str], page_width: float, page_height: float) -> float:
    page_area = max(1.0, page_width * page_height)
    area = 0.0
    for block in blocks:
        if block["role"] in roles:
            bbox = block["bbox"]
            area += max(0.0, safe_float(bbox["x2"]) - safe_float(bbox["x1"])) * max(
                0.0, safe_float(bbox["y2"]) - safe_float(bbox["y1"])
            )
    return min(1.0, area / page_area)


def assign_layout_type_and_columns(blocks: list[dict[str, Any]], page_width: float, page_height: float) -> str:
    role_counts = compute_role_counts(blocks)
    visual_area_ratio = compute_area_ratio(blocks, VISUAL_ROLES, page_width, page_height)
    handwriting_ratio = sum(
        1 for block in blocks if "formula_reclassified_as_handwriting_body" in block.get("notes", [])
    ) / max(1, len(blocks))
    text_candidates = [
        block
        for block in blocks
        if block["role"] in {"body", "subtitle", "caption"}
        and block["reading_group"] != "noise"
        and block_area_ratio(block, page_width, page_height) < 0.35
    ]

    if handwriting_ratio >= 0.5:
        assign_single_column(blocks)
        return "single_column"

    if visual_area_ratio >= 0.55 and len(text_candidates) <= 5:
        assign_single_column(blocks)
        return "image_dominant"

    if visual_area_ratio >= 0.10 and len(text_candidates) >= 10 and len(blocks) >= 20:
        assign_single_column(blocks)
        return "mixed_complex"

    if len(text_candidates) < 4:
        assign_single_column(blocks)
        return "single_column"

    clusters = cluster_by_center_x(text_candidates, page_width)
    if len(clusters) == 1:
        assign_single_column(blocks)
        return "single_column"
    if len(clusters) == 2 and all(len(cluster) >= 2 for cluster in clusters):
        assign_double_columns(blocks, clusters, page_width)
        if visual_area_ratio >= 0.25 and (role_counts.get("figure", 0) + role_counts.get("table", 0)) >= 2:
            return "mixed_complex"
        return "double_column"

    assign_columns_from_clusters(blocks, clusters)
    if len(clusters) >= 3:
        return "multi_column"
    return "mixed_complex"


def block_area_ratio(block: dict[str, Any], page_width: float, page_height: float) -> float:
    bbox = block["bbox"]
    area = max(0.0, safe_float(bbox["x2"]) - safe_float(bbox["x1"])) * max(
        0.0, safe_float(bbox["y2"]) - safe_float(bbox["y1"])
    )
    return area / max(1.0, page_width * page_height)


def cluster_by_center_x(blocks: list[dict[str, Any]], page_width: float) -> list[list[dict[str, Any]]]:
    sorted_blocks = sorted(blocks, key=lambda block: block_center_x(block))
    if not sorted_blocks:
        return []

    threshold = max(80.0, page_width * 0.18)
    clusters: list[list[dict[str, Any]]] = [[sorted_blocks[0]]]
    for block in sorted_blocks[1:]:
        previous_cluster = clusters[-1]
        previous_center = sum(block_center_x(item) for item in previous_cluster) / len(previous_cluster)
        if abs(block_center_x(block) - previous_center) <= threshold:
            previous_cluster.append(block)
        else:
            clusters.append([block])

    # Merge tiny edge clusters into nearest larger cluster to avoid over-splitting icon/button text.
    merged: list[list[dict[str, Any]]] = []
    for cluster in clusters:
        if len(cluster) == 1 and merged:
            merged[-1].extend(cluster)
        else:
            merged.append(cluster)
    return merged


def block_center_x(block: dict[str, Any]) -> float:
    bbox = block["bbox"]
    return (safe_float(bbox["x1"]) + safe_float(bbox["x2"])) / 2


def assign_single_column(blocks: list[dict[str, Any]]) -> None:
    for block in blocks:
        if block["reading_group"] != "noise":
            block["column"] = 1


def assign_double_columns(blocks: list[dict[str, Any]], clusters: list[list[dict[str, Any]]], page_width: float) -> None:
    sorted_clusters = sorted(clusters, key=lambda cluster: sum(block_center_x(block) for block in cluster) / len(cluster))
    membership: dict[str, int] = {}
    for column, cluster in enumerate(sorted_clusters, start=1):
        for block in cluster:
            membership[block["block_id"]] = column

    for block in blocks:
        if block["reading_group"] == "noise":
            continue
        width_ratio = (safe_float(block["bbox"]["x2"]) - safe_float(block["bbox"]["x1"])) / max(1.0, page_width)
        if width_ratio >= 0.55 and block["role"] in {"title", "subtitle"}:
            block["column"] = 0
        else:
            block["column"] = membership.get(block["block_id"], nearest_cluster_column(block, sorted_clusters))


def assign_columns_from_clusters(blocks: list[dict[str, Any]], clusters: list[list[dict[str, Any]]]) -> None:
    if not clusters:
        assign_single_column(blocks)
        return
    sorted_clusters = sorted(clusters, key=lambda cluster: sum(block_center_x(block) for block in cluster) / len(cluster))
    for block in blocks:
        if block["reading_group"] == "noise":
            continue
        block["column"] = nearest_cluster_column(block, sorted_clusters)


def nearest_cluster_column(block: dict[str, Any], clusters: list[list[dict[str, Any]]]) -> int:
    center = block_center_x(block)
    distances = []
    for index, cluster in enumerate(clusters, start=1):
        cluster_center = sum(block_center_x(item) for item in cluster) / len(cluster)
        distances.append((abs(center - cluster_center), index))
    return min(distances)[1] if distances else 1


def assign_order(blocks: list[dict[str, Any]], layout_type: str, page_width: float) -> None:
    ordered_blocks = [block for block in blocks if not block["is_noise"]]

    if layout_type == "double_column":
        sorted_blocks = sorted(ordered_blocks, key=lambda block: double_column_sort_key(block, page_width))
    else:
        sorted_blocks = sorted(ordered_blocks, key=visual_sort_key)

    for order, block in enumerate(sorted_blocks, start=1):
        block["order"] = order


def visual_sort_key(block: dict[str, Any]) -> tuple[float, float, int]:
    group_priority = reading_group_priority(block)
    return (safe_float(block["bbox"]["y1"]), safe_float(block["bbox"]["x1"]), group_priority)


def double_column_sort_key(block: dict[str, Any], page_width: float) -> tuple[int, int, float, float]:
    bbox = block["bbox"]
    width_ratio = (safe_float(bbox["x2"]) - safe_float(bbox["x1"])) / max(1.0, page_width)
    if block["role"] in {"title", "subtitle"} and width_ratio >= 0.55:
        return (0, 0, safe_float(bbox["y1"]), safe_float(bbox["x1"]))
    column = int(block.get("column") or 1)
    return (1, column, safe_float(bbox["y1"]), safe_float(bbox["x1"]))


def reading_group_priority(block: dict[str, Any]) -> int:
    role = block["role"]
    group = block["reading_group"]
    if role in {"title", "subtitle"}:
        return 0
    if group == "main":
        return 1
    if group == "caption":
        return 2
    if group == "visual":
        return 3
    if group in {"sidebar", "note"}:
        return 4
    return 5


def infer_page_type(blocks: list[dict[str, Any]], layout_type: str, page_width: float, page_height: float) -> str:
    counts = compute_role_counts(blocks)
    total = max(1, len(blocks))
    formula_count = counts.get("formula", 0)
    table_count = counts.get("table", 0)
    figure_count = counts.get("figure", 0)
    body_count = counts.get("body", 0)
    text_block_count = sum(counts.get(role, 0) for role in ("body", "subtitle", "title", "caption"))
    visual_area_ratio = compute_area_ratio(blocks, VISUAL_ROLES, page_width, page_height)
    table_area_ratio = compute_area_ratio(blocks, {"table"}, page_width, page_height)

    handwriting_note_count = sum(
        1 for block in blocks if "formula_reclassified_as_handwriting_body" in block.get("notes", [])
    )
    if handwriting_note_count / total >= 0.5:
        return "handwriting"
    if table_count >= 1 or table_area_ratio >= 0.15:
        return "form_or_resume"
    if visual_area_ratio >= 0.25 and text_block_count >= 6:
        return "magazine_complex"
    if layout_type in {"multi_column", "mixed_complex"} and figure_count + table_count + formula_count >= 2:
        return "magazine_complex"
    if layout_type == "double_column" and text_block_count >= 6 and visual_area_ratio < 0.35:
        return "paper"
    if layout_type == "single_column" and body_count >= 2 and visual_area_ratio < 0.25:
        return "book_text"
    if visual_area_ratio >= 0.25:
        return "magazine_simple"
    return "unknown"


def compute_complexity(
    blocks: list[dict[str, Any]],
    layout_type: str,
    page_type: str,
    page_width: float,
    page_height: float,
) -> dict[str, Any]:
    score = 0.0
    reasons: list[str] = []
    counts = compute_role_counts(blocks)
    total = max(1, len(blocks))
    visual_area_ratio = compute_area_ratio(blocks, VISUAL_ROLES, page_width, page_height)
    text_count = sum(counts.get(role, 0) for role in ("body", "subtitle", "title", "caption"))
    unknown_ratio = counts.get("unknown", 0) / total
    low_confidence_ratio = sum(1 for block in blocks if block["confidence"]["detector"] < 0.60) / total

    def add(value: float, reason: str) -> None:
        nonlocal score
        score += value
        reasons.append(reason)

    if visual_area_ratio >= 0.40:
        add(0.30, "visual_area_ratio_gt_0.40")
    elif visual_area_ratio >= 0.25:
        add(0.20, "visual_area_ratio_gt_0.25")
    if text_count >= 20:
        add(0.15, "many_text_blocks")
    if total >= 30:
        add(0.15, "many_blocks")
    if layout_type == "multi_column":
        add(0.20, "multi_column")
    if layout_type == "mixed_complex":
        add(0.30, "mixed_complex")
    if unknown_ratio >= 0.20:
        add(0.15, "many_unknown_blocks")
    if low_confidence_ratio >= 0.25:
        add(0.10, "many_low_confidence_blocks")
    if counts.get("header", 0) and counts.get("footer", 0):
        add(0.05, "has_header_footer")
    if page_type == "form_or_resume":
        add(0.10, "has_table")
    if page_type == "handwriting":
        add(0.15, "handwriting_page")

    score = round4(min(score, 1.0))
    level = "low"
    if score >= 0.65:
        level = "high"
    elif score >= 0.35:
        level = "medium"

    need_vlm = level == "high"
    if page_type == "magazine_complex" and score >= 0.5:
        need_vlm = True
    if layout_type == "mixed_complex":
        need_vlm = True
    if unknown_ratio > 0.30:
        need_vlm = True

    return {
        "level": level,
        "score": score,
        "reasons": reasons,
        "need_vlm": need_vlm,
        "metrics": {
            "visual_area_ratio": round4(visual_area_ratio),
            "unknown_ratio": round4(unknown_ratio),
            "low_confidence_ratio": round4(low_confidence_ratio),
            "text_block_count": text_count,
            "total_block_count": total,
        },
    }


def refine_page(page_data: dict[str, Any]) -> dict[str, Any]:
    page_width = safe_float(page_data.get("width"))
    page_height = safe_float(page_data.get("height"))
    blocks = create_initial_blocks(page_data)
    layout_type = assign_layout_type_and_columns(blocks, page_width, page_height)
    page_type = infer_page_type(blocks, layout_type, page_width, page_height)
    complexity = compute_complexity(blocks, layout_type, page_type, page_width, page_height)
    assign_order(blocks, layout_type, page_width)

    return {
        "task_id": page_data.get("task_id"),
        "page_no": page_data.get("page_no"),
        "image_path": page_data.get("image_path"),
        "width": page_data.get("width"),
        "height": page_data.get("height"),
        "page_type": page_type,
        "layout_type": layout_type,
        "complexity": complexity,
        "blocks": sorted(blocks, key=lambda block: block["block_id"]),
    }


def collect_raw_pages(task_dir: Path) -> list[Path]:
    raw_dir = task_dir / "layout_raw"
    if not raw_dir.exists():
        raise FileNotFoundError(f"layout_raw directory does not exist: {raw_dir}")
    pages = sorted(path for path in raw_dir.glob("page_*.json") if path.name != "summary.json")
    if not pages:
        raise FileNotFoundError(f"No layout_raw page JSON files found in: {raw_dir}")
    return pages


def summarize_layout_pages(pages: list[dict[str, Any]], task_dir: Path, started_at: datetime) -> dict[str, Any]:
    page_summaries: list[dict[str, Any]] = []
    type_counts: dict[str, int] = {}
    layout_counts: dict[str, int] = {}
    role_counts_total: dict[str, int] = {}
    need_vlm_count = 0

    for page in pages:
        role_counts = compute_role_counts(page["blocks"])
        for role, count in role_counts.items():
            role_counts_total[role] = role_counts_total.get(role, 0) + count
        page_type = str(page["page_type"])
        layout_type = str(page["layout_type"])
        type_counts[page_type] = type_counts.get(page_type, 0) + 1
        layout_counts[layout_type] = layout_counts.get(layout_type, 0) + 1
        if page["complexity"]["need_vlm"]:
            need_vlm_count += 1

        page_summaries.append(
            {
                "page_no": page["page_no"],
                "layout_path": project_relative(task_dir / "layout" / f"page_{int(page['page_no']):03d}.json"),
                "page_type": page_type,
                "layout_type": layout_type,
                "complexity": {
                    "level": page["complexity"]["level"],
                    "score": page["complexity"]["score"],
                    "need_vlm": page["complexity"]["need_vlm"],
                    "reasons": page["complexity"]["reasons"],
                },
                "block_count": len(page["blocks"]),
                "role_counts": role_counts,
            }
        )

    return {
        "task_id": task_dir.name,
        "task_dir": project_relative(task_dir),
        "stage": "layout_refined",
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "page_count": len(pages),
        "need_vlm_page_count": need_vlm_count,
        "page_type_counts": type_counts,
        "layout_type_counts": layout_counts,
        "role_counts": role_counts_total,
        "pages": page_summaries,
    }


def refine_task_layout(task_dir: Path) -> dict[str, Any]:
    started_at = datetime.now()
    refined_pages: list[dict[str, Any]] = []
    for raw_path in collect_raw_pages(task_dir):
        page = refine_page(load_json(raw_path))
        refined_pages.append(page)
        page_no = int(page["page_no"])
        write_json(task_dir / "layout" / f"page_{page_no:03d}.json", page)

    summary = summarize_layout_pages(refined_pages, task_dir, started_at)
    write_json(task_dir / "layout" / "summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refine layout_raw JSON files into normalized layout JSON files.")
    parser.add_argument("task", help="Task ID under backend/storage/tasks, or an explicit task directory path.")
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
        help=f"Directory that stores task folders. Default: {DEFAULT_STORAGE_ROOT}",
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
        summary = refine_task_layout(task_dir)
    except Exception as exc:
        print(f"Layout refinement failed: {exc}")
        return 1

    print(f"Refined {summary['page_count']} page(s).")
    print(f"Task ID: {summary['task_id']}")
    print(f"Need VLM pages: {summary['need_vlm_page_count']}")
    print(f"Summary: {summary['task_dir']}/layout/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
