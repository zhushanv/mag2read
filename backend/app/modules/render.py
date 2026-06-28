#!/usr/bin/env python3
"""Render PDF pages or image inputs to PNG files for the OCR pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from pathlib import Path

try:
    from PIL import Image, ImageOps, ImageStat
except ImportError as exc:
    raise SystemExit(
        "Pillow is not installed in the current Python environment. "
        "Install it with: conda run -n industrial-cv pip install Pillow"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = PROJECT_ROOT / "pdfs" / "pdf1.0.pdf"
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "backend" / "storage" / "tasks"
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass
class RenderedPage:
    page_no: int
    image_path: str
    width: int
    height: int
    dpi: int | None
    source_path: str
    source_type: str
    quality: dict[str, Any]
    render_seconds: float


def parse_page_range(value: str | None, total_pages: int) -> list[int]:
    if not value:
        return list(range(total_pages))

    selected: set[int] = set()
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"Invalid page range: {item}")
            selected.update(range(start, end + 1))
        else:
            selected.add(int(item))

    invalid_pages = [page for page in selected if page < 1 or page > total_pages]
    if invalid_pages:
        raise ValueError(
            f"Page number out of range: {invalid_pages}. "
            f"The PDF has {total_pages} page(s)."
        )

    return [page - 1 for page in sorted(selected)]


def build_task_id(task_id: str | None) -> str:
    if task_id:
        return task_id
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def prepare_task_dir(task_dir: Path, overwrite: bool) -> Path:
    pages_dir = task_dir / "pages"
    if task_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Task directory already exists: {task_dir}. "
                "Use --overwrite or choose another --task-id."
            )
        shutil.rmtree(task_dir)

    pages_dir.mkdir(parents=True, exist_ok=True)
    return pages_dir


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def analyze_image_quality(image: Image.Image) -> dict[str, Any]:
    width, height = image.size
    pixel_count = width * height
    aspect_ratio = round(width / height, 4) if height else 0
    orientation = "portrait"
    if width > height:
        orientation = "landscape"
    elif width == height:
        orientation = "square"

    gray = ImageOps.grayscale(image)
    stat = ImageStat.Stat(gray)
    brightness = round(stat.mean[0], 2)
    contrast = round(stat.stddev[0], 2)

    issues: list[str] = []
    warnings: list[str] = []

    if min(width, height) < 800 or pixel_count < 1_000_000:
        issues.append("small_image")
    if orientation == "landscape":
        warnings.append("landscape_orientation")
    if aspect_ratio > 2.2 or aspect_ratio < 0.45:
        warnings.append("extreme_aspect_ratio")
    if brightness > 245 and contrast < 8:
        issues.append("blank_or_nearly_blank_light_page")
    elif brightness < 10 and contrast < 8:
        issues.append("blank_or_nearly_blank_dark_page")
    elif contrast < 12:
        issues.append("very_low_contrast")
    elif contrast < 30:
        warnings.append("low_contrast")
    if brightness < 50:
        issues.append("too_dark")
    elif brightness < 75:
        warnings.append("dark_page")

    status = "ok"
    if warnings:
        status = "warning"
    if issues:
        status = "review"

    return {
        "status": status,
        "orientation": orientation,
        "width": width,
        "height": height,
        "pixel_count": pixel_count,
        "aspect_ratio": aspect_ratio,
        "brightness": brightness,
        "contrast": contrast,
        "issues": issues,
        "warnings": warnings,
    }


def build_quality_summary(rendered_pages: list[RenderedPage]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    warning_counts: dict[str, int] = {}
    pages_with_issues = 0
    pages_with_warnings = 0

    for page in rendered_pages:
        quality = page.quality
        status = str(quality.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        issues = quality.get("issues", [])
        warnings = quality.get("warnings", [])
        if issues:
            pages_with_issues += 1
        if warnings:
            pages_with_warnings += 1
        for issue in issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        for warning in warnings:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1

    return {
        "status_counts": status_counts,
        "issue_counts": issue_counts,
        "warning_counts": warning_counts,
        "needs_review_page_count": status_counts.get("review", 0),
        "warning_page_count": status_counts.get("warning", 0),
        "pages_with_issues_count": pages_with_issues,
        "pages_with_warnings_count": pages_with_warnings,
    }


def collect_image_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError(f"Unsupported image file: {input_path}")
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    images = [
        path
        for path in sorted(input_path.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    ]
    if not images:
        raise ValueError(f"No supported image files found in directory: {input_path}")
    return images


def copy_input_files(input_path: Path, task_dir: Path, source_files: list[Path]) -> None:
    input_dir = task_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        shutil.copy2(input_path, input_dir / "original.pdf")
        return

    for source_file in source_files:
        shutil.copy2(source_file, input_dir / source_file.name)


def import_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is not installed in the current Python environment. "
            "Install it with: conda run -n industrial-cv pip install pymupdf"
        ) from exc
    return fitz


def render_pdf_pages(
    pdf_path: Path,
    task_dir: Path,
    dpi: int,
    page_range: str | None,
    overwrite: bool,
    copy_input: bool,
) -> dict:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Input file must be a PDF: {pdf_path}")
    if dpi <= 0:
        raise ValueError("DPI must be a positive integer.")

    fitz = import_fitz()
    pages_dir = prepare_task_dir(task_dir, overwrite=overwrite)
    started_at = datetime.now()
    rendered_pages: list[RenderedPage] = []

    with fitz.open(pdf_path) as document:
        page_indexes = parse_page_range(page_range, document.page_count)
        matrix = fitz.Matrix(dpi / 72, dpi / 72)

        for page_index in page_indexes:
            page = document.load_page(page_index)
            render_start = time.perf_counter()
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output_path = pages_dir / f"page_{page_index + 1:03d}.png"
            pixmap.save(output_path)
            with Image.open(output_path) as rendered_image:
                quality = analyze_image_quality(rendered_image)
            render_seconds = time.perf_counter() - render_start

            rendered_pages.append(
                RenderedPage(
                    page_no=page_index + 1,
                    image_path=project_relative(output_path),
                    width=pixmap.width,
                    height=pixmap.height,
                    dpi=dpi,
                    source_path=project_relative(pdf_path),
                    source_type="pdf_page",
                    quality=quality,
                    render_seconds=round(render_seconds, 4),
                )
            )

        metadata = {
            "task_id": task_dir.name,
            "input_type": "pdf",
            "source_pdf": project_relative(pdf_path),
            "source_files": [project_relative(pdf_path)],
            "task_dir": project_relative(task_dir),
            "dpi": dpi,
            "total_pdf_pages": document.page_count,
            "rendered_page_count": len(rendered_pages),
            "created_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "quality_summary": build_quality_summary(rendered_pages),
            "pages": [asdict(page) for page in rendered_pages],
        }

    if copy_input:
        copy_input_files(pdf_path, task_dir, [pdf_path])

    metadata_path = task_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def render_image_pages(
    image_input_path: Path,
    task_dir: Path,
    overwrite: bool,
    copy_input: bool,
) -> dict:
    image_paths = collect_image_inputs(image_input_path)
    pages_dir = prepare_task_dir(task_dir, overwrite=overwrite)
    started_at = datetime.now()
    rendered_pages: list[RenderedPage] = []

    for page_index, image_path in enumerate(image_paths, start=1):
        render_start = time.perf_counter()
        output_path = pages_dir / f"page_{page_index:03d}.png"

        with Image.open(image_path) as image:
            normalized = ImageOps.exif_transpose(image)
            if normalized.mode != "RGB":
                normalized = normalized.convert("RGB")
            normalized.save(output_path, format="PNG")
            width, height = normalized.size
            quality = analyze_image_quality(normalized)

        render_seconds = time.perf_counter() - render_start
        rendered_pages.append(
            RenderedPage(
                page_no=page_index,
                image_path=project_relative(output_path),
                width=width,
                height=height,
                dpi=None,
                source_path=project_relative(image_path),
                source_type="image",
                quality=quality,
                render_seconds=round(render_seconds, 4),
            )
        )

    metadata = {
        "task_id": task_dir.name,
        "input_type": "image_directory" if image_input_path.is_dir() else "image",
        "source_files": [project_relative(path) for path in image_paths],
        "task_dir": project_relative(task_dir),
        "dpi": None,
        "total_pdf_pages": None,
        "rendered_page_count": len(rendered_pages),
        "created_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "quality_summary": build_quality_summary(rendered_pages),
        "pages": [asdict(page) for page in rendered_pages],
    }

    if copy_input:
        copy_input_files(image_input_path, task_dir, image_paths)

    metadata_path = task_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def render_input_pages(
    input_path: Path,
    task_dir: Path,
    dpi: int,
    page_range: str | None,
    overwrite: bool,
    copy_input: bool,
) -> dict:
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        return render_pdf_pages(
            pdf_path=input_path,
            task_dir=task_dir,
            dpi=dpi,
            page_range=page_range,
            overwrite=overwrite,
            copy_input=copy_input,
        )

    if page_range:
        raise ValueError("--pages can only be used with PDF inputs.")

    return render_image_pages(
        image_input_path=input_path,
        task_dir=task_dir,
        overwrite=overwrite,
        copy_input=copy_input,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render PDF pages or normalize image inputs to PNG pages for later OCR processing."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(DEFAULT_INPUT),
        help=f"Input PDF, image file, or image directory. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
        help=f"Directory that stores task folders. Default: {DEFAULT_STORAGE_ROOT}",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="Task ID used as the output folder name. Default: timestamp plus random suffix.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Render DPI. 200 is faster; 300 is clearer but larger. Default: 200.",
    )
    parser.add_argument(
        "--pages",
        default=None,
        help="PDF pages to render, using 1-based numbers. Examples: 1, 1-3, 1,3,5-7.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the existing task directory if it already exists.",
    )
    parser.add_argument(
        "--no-copy-input",
        action="store_true",
        help="Do not copy the source PDF to the task directory as input.pdf.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    storage_root = Path(args.storage_root).expanduser().resolve()
    task_id = build_task_id(args.task_id)
    task_dir = storage_root / task_id

    try:
        metadata = render_input_pages(
            input_path=input_path,
            task_dir=task_dir,
            dpi=args.dpi,
            page_range=args.pages,
            overwrite=args.overwrite,
            copy_input=not args.no_copy_input,
        )
    except Exception as exc:
        print(f"Render failed: {exc}", file=sys.stderr)
        return 1

    print(f"Rendered {metadata['rendered_page_count']} page(s).")
    print(f"Task ID: {metadata['task_id']}")
    print(f"Output: {metadata['task_dir']}")
    print(f"Metadata: {metadata['task_dir']}/metadata.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
