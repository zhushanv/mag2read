from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings
from backend.app.core.database import SessionLocal
from backend.app.modules.baidu_paddle_vl import BaiduPaddleVlOptions, run_baidu_paddle_vl
from backend.app.modules.document_build import build_document, write_outputs
from backend.app.modules.export_document import run_export
from backend.app.modules.layout_detect import analyze_task_layout
from backend.app.modules.layout_refine import refine_task_layout
from backend.app.modules.media_builder import build_media_assets
from backend.app.modules.ocr import run_task_ocr
from backend.app.modules.render import render_input_pages
from backend.app.modules.text_cleaning import run_cleaning
from backend.app.schemas.task import ExportRecordCreate, TaskFileCreate, TaskPageCreate, TaskStepUpsert
from backend.app.services import task_service
from backend.app.services.enums import TaskStage, TaskStatus
from backend.app.workers.celery_app import celery_app


@celery_app.task(name="stage0.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="pipeline.process_uploaded_task")
def process_uploaded_task(task_id: str) -> dict[str, Any]:
    settings = get_settings()
    db = SessionLocal()
    current_stage: TaskStage | None = None
    try:
        task = task_service.get_task(db, task_id)
        if task is None:
            raise ValueError(f"Task does not exist: {task_id}")

        task_service.mark_task_processing(db, task, stage=None, progress=0)
        task_dir = Path(task.storage_dir)
        input_path = find_input_file(db, task_id)
        metadata = read_task_metadata(task_dir)
        requested_mode = str(metadata.get("processing_mode") or "auto").lower()
        processing_mode = resolve_processing_mode(requested_mode, task.input_type)
        write_task_metadata(
            task_dir,
            {
                "processing_mode_requested": requested_mode,
                "processing_mode": processing_mode,
                "processing_provider": "baidu_paddle_vl" if processing_mode == "cloud" else "local_paddle",
                "pipeline_started_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

        results: dict[str, Any] = {}
        current_stage = TaskStage.RENDER
        results["render"] = run_pipeline_stage(
            db,
            task_id,
            TaskStage.RENDER,
            lambda: run_render_stage(input_path=input_path, task_dir=task_dir, settings=settings, task_input_type=task.input_type),
        )
        record_render_outputs(db, task_id, results["render"])

        current_stage = None
        if processing_mode == "cloud":
            results.update(run_cloud_recognition_stages(db, task_id, task_dir, input_path, settings, input_file=project_relative(input_path)))
        else:
            results.update(run_local_recognition_stages(db, task_id, task_dir, settings))
        results["media"] = build_media_assets(task_dir)
        record_media_files(db, task_id, task_dir)

        current_stage = TaskStage.TEXT_CLEANING
        results["text_cleaning"] = run_pipeline_stage(
            db,
            task_id,
            TaskStage.TEXT_CLEANING,
            lambda: run_cleaning(task_dir),
        )
        record_clean_files(db, task_id, task_dir)

        current_stage = TaskStage.DOCUMENT_BUILD
        results["document_build"] = run_pipeline_stage(
            db,
            task_id,
            TaskStage.DOCUMENT_BUILD,
            lambda: write_outputs(task_dir, build_document(task_dir)),
        )
        record_markdown_file(db, task_id, task_dir)

        current_stage = TaskStage.EXPORT
        export_formats = parse_output_formats(task.output_format)
        results["export"] = run_pipeline_stage(
            db,
            task_id,
            TaskStage.EXPORT,
            lambda: run_export(task_dir, export_formats),
        )
        record_exports(db, task_id, results["export"])

        refreshed_task = task_service.get_task(db, task_id)
        if refreshed_task is not None:
            task_service.mark_task_success(db, refreshed_task)
        return {"task_id": task_id, "status": "success", "results": results}
    except Exception as exc:
        if current_stage is not None:
            task_service.upsert_task_step(
                db,
                task_id,
                TaskStepUpsert(
                    stage=current_stage,
                    status=TaskStatus.FAILED,
                    progress=0,
                    error_message=str(exc),
                ),
            )
        task = task_service.get_task(db, task_id)
        if task is not None:
            task_service.mark_task_failed(db, task, current_stage.value if current_stage else None, str(exc))
        raise
    finally:
        db.close()


def run_local_recognition_stages(db, task_id: str, task_dir: Path, settings) -> dict[str, Any]:
    results: dict[str, Any] = {}
    results["layout_detect"] = run_pipeline_stage(
        db,
        task_id,
        TaskStage.LAYOUT_DETECT,
        lambda: analyze_task_layout(
            task_dir=task_dir,
            cache_dir=Path(settings.paddlex_cache_root),
            threshold=None,
            draw_debug=True,
        ),
    )
    record_stage_files(db, task_id, task_dir / "layout_raw", "layout_raw_json")

    results["layout_refine"] = run_pipeline_stage(
        db,
        task_id,
        TaskStage.LAYOUT_REFINE,
        lambda: refine_task_layout(task_dir),
    )
    record_stage_files(db, task_id, task_dir / "layout", "layout_json")

    results["ocr"] = run_pipeline_stage(
        db,
        task_id,
        TaskStage.OCR,
        lambda: run_task_ocr(
            task_dir=task_dir,
            cache_dir=Path(settings.paddlex_cache_root),
            padding=4,
            include_unknown=False,
            save_crops=False,
            use_textline_orientation=False,
        ),
    )
    record_stage_files(db, task_id, task_dir / "ocr", "ocr_json")
    return results


def run_cloud_recognition_stages(db, task_id: str, task_dir: Path, input_path: Path, settings, input_file: str) -> dict[str, Any]:
    mark_stage_skipped(
        db,
        task_id,
        TaskStage.LAYOUT_DETECT,
        {"provider": "baidu_paddle_vl", "reason": "cloud mode uses Baidu layout analysis"},
    )
    mark_stage_skipped(
        db,
        task_id,
        TaskStage.LAYOUT_REFINE,
        {"provider": "baidu_paddle_vl", "reason": "cloud mode converts Baidu layouts directly"},
    )
    result = run_pipeline_stage(
        db,
        task_id,
        TaskStage.OCR,
        lambda: run_baidu_paddle_vl(
            input_path=input_path,
            task_dir=task_dir,
            options=BaiduPaddleVlOptions(
                api_key=settings.baidu_ocr_api_key,
                secret_key=settings.baidu_ocr_secret_key,
                access_token=settings.baidu_ocr_access_token,
                poll_interval=8,
                timeout_seconds=900,
                http_timeout=60,
            ),
            file_name=input_path.name,
            input_file=input_file,
        ),
    )
    record_stage_files(db, task_id, task_dir / "layout", "layout_json")
    record_stage_files(db, task_id, task_dir / "ocr", "ocr_json")
    return {"layout_detect": {"status": "skipped"}, "layout_refine": {"status": "skipped"}, "ocr": result}


def run_pipeline_stage(db, task_id: str, stage: TaskStage, fn):
    started = time.perf_counter()
    task_service.upsert_task_step(
        db,
        task_id,
        TaskStepUpsert(stage=stage, status=TaskStatus.PROCESSING, progress=0),
    )
    try:
        result = fn()
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        task_service.upsert_task_step(
            db,
            task_id,
            TaskStepUpsert(
                stage=stage,
                status=TaskStatus.FAILED,
                progress=0,
                duration_ms=duration_ms,
                error_message=str(exc),
            ),
        )
        raise

    duration_ms = int((time.perf_counter() - started) * 1000)
    task_service.upsert_task_step(
        db,
        task_id,
        TaskStepUpsert(
            stage=stage,
            status=TaskStatus.SUCCESS,
            progress=100,
            duration_ms=duration_ms,
            summary_json=summarize_result(result),
        ),
    )
    return result


def find_input_file(db, task_id: str) -> Path:
    files = task_service.list_task_files(db, task_id)
    for file in files:
        if file.file_role in {"input_pdf", "input_image"}:
            return Path(file.file_path)
    raise FileNotFoundError(f"No input file record found for task: {task_id}")


def project_relative(path: Path) -> str:
    project_root = Path(__file__).resolve().parents[3]
    return str(path.relative_to(project_root)) if path.is_relative_to(project_root) else str(path)


def read_task_metadata(task_dir: Path) -> dict[str, Any]:
    path = task_dir / "metadata.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_task_metadata(task_dir: Path, updates: dict[str, Any]) -> None:
    metadata = read_task_metadata(task_dir)
    metadata.update(updates)
    path = task_dir / "metadata.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

# Processing mode: local, cloud, or auto
def resolve_processing_mode(requested_mode: str, input_type: str) -> str:
    if requested_mode in {"local", "cloud"}:
        return requested_mode
    if input_type == "pdf":
        return "cloud"
    return "local"


def mark_stage_skipped(db, task_id: str, stage: TaskStage, summary: dict[str, Any]) -> None:
    task_service.upsert_task_step(
        db,
        task_id,
        TaskStepUpsert(
            stage=stage,
            status=TaskStatus.SKIPPED,
            progress=100,
            summary_json=summary,
        ),
    )


def run_render_stage(input_path: Path, task_dir: Path, settings, task_input_type: str) -> dict[str, Any]:
    return render_input_pages(
        input_path=input_path,
        task_dir=task_dir,
        dpi=200,
        page_range=None,
        overwrite=True,
        copy_input=False,
        reset_task_dir=False,
    )


def summarize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        if "ocr_summary" in result and isinstance(result["ocr_summary"], dict):
            ocr_summary = result["ocr_summary"]
            return {
                "provider": ocr_summary.get("provider"),
                "page_count": ocr_summary.get("page_count"),
                "ocr_block_count": ocr_summary.get("ocr_block_count"),
                "recognized_block_count": ocr_summary.get("recognized_block_count"),
                "line_count": ocr_summary.get("line_count"),
            }
        summary = {}
        for key in (
            "stage",
            "page_count",
            "rendered_page_count",
            "total_raw_blocks",
            "ocr_block_count",
            "recognized_block_count",
            "output_blocks",
            "avg_confidence",
            "need_vlm_page_count",
        ):
            if key in result:
                summary[key] = result[key]
        if "timing" in result:
            timing = result["timing"]
            summary["timing"] = {
                key: timing.get(key)
                for key in (
                    "ocr_model_init_seconds",
                    "total_ocr_seconds",
                    "total_page_ocr_seconds",
                    "total_block_seconds",
                    "total_predict_seconds",
                    "avg_page_ocr_seconds",
                    "avg_block_seconds",
                    "avg_predict_seconds",
                    "max_page_ocr_seconds",
                    "max_block_seconds",
                    "max_predict_seconds",
                    "slow_block_count",
                    "slow_blocks",
                    "models_added",
                    "paddlex_cache_dir",
                )
                if key in timing
            }
        return summary or {"result_type": "dict"}
    return {"result_type": type(result).__name__}


def record_render_outputs(db, task_id: str, metadata: dict[str, Any]) -> None:
    for page in metadata.get("pages", []):
        task_service.add_task_page(
            db,
            task_id,
            TaskPageCreate(
                page_no=int(page["page_no"]),
                image_path=str(page["image_path"]),
                width=page.get("width"),
                height=page.get("height"),
                quality_status=(page.get("quality") or {}).get("status"),
                need_review=(page.get("quality") or {}).get("status") == "review",
            ),
        )
        task_service.add_task_file(
            db,
            task_id,
            TaskFileCreate(
                file_role="page_image",
                file_name=Path(str(page["image_path"])).name,
                file_path=str(page["image_path"]),
                mime_type="image/png",
                file_size=None,
                page_no=int(page["page_no"]),
            ),
        )


def record_stage_files(db, task_id: str, directory: Path, file_role: str) -> None:
    if not directory.exists():
        return
    for path in sorted(directory.glob("*.json")):
        page_no = parse_page_no(path)
        task_service.add_task_file(
            db,
            task_id,
            TaskFileCreate(
                file_role=file_role,
                file_name=path.name,
                file_path=str(path),
                mime_type="application/json",
                file_size=path.stat().st_size,
                page_no=page_no,
            ),
        )


def record_clean_files(db, task_id: str, task_dir: Path) -> None:
    clean_dir = task_dir / "clean"
    roles = {
        "document.json": "clean_json",
        "cleaning_report.json": "cleaning_report",
    }
    for filename, role in roles.items():
        path = clean_dir / filename
        if path.exists():
            task_service.add_task_file(
                db,
                task_id,
                TaskFileCreate(
                    file_role=role,
                    file_name=path.name,
                    file_path=str(path),
                    mime_type="application/json",
                    file_size=path.stat().st_size,
                ),
            )


def record_markdown_file(db, task_id: str, task_dir: Path) -> None:
    path = task_dir / "clean" / "book.md"
    if path.exists():
        task_service.add_task_file(
            db,
            task_id,
            TaskFileCreate(
                file_role="markdown",
                file_name=path.name,
                file_path=str(path),
                mime_type="text/markdown",
                file_size=path.stat().st_size,
            ),
        )


def record_media_files(db, task_id: str, task_dir: Path) -> None:
    media_dir = task_dir / "media"
    if not media_dir.exists():
        return
    for path in sorted(media_dir.glob("*.png")):
        task_service.add_task_file(
            db,
            task_id,
            TaskFileCreate(
                file_role="media_image",
                file_name=path.name,
                file_path=str(path),
                mime_type="image/png",
                file_size=path.stat().st_size,
                page_no=parse_page_no(path),
            ),
        )
    summary_path = media_dir / "summary.json"
    if summary_path.exists():
        task_service.add_task_file(
            db,
            task_id,
            TaskFileCreate(
                file_role="media_summary",
                file_name=summary_path.name,
                file_path=str(summary_path),
                mime_type="application/json",
                file_size=summary_path.stat().st_size,
            ),
        )


def record_exports(db, task_id: str, exports: dict[str, str]) -> None:
    for fmt, file_path in exports.items():
        path = Path(file_path)
        task_service.add_export_record(
            db,
            task_id,
            ExportRecordCreate(
                format=fmt,
                file_path=str(path),
                file_size=path.stat().st_size if path.exists() else None,
                status=TaskStatus.SUCCESS,
            ),
        )
        task_service.add_task_file(
            db,
            task_id,
            TaskFileCreate(
                file_role=fmt,
                file_name=path.name,
                file_path=str(path),
                mime_type=mime_type_for_export(fmt),
                file_size=path.stat().st_size if path.exists() else None,
            ),
        )


def parse_output_formats(value: str | None) -> list[str]:
    if not value:
        return ["epub"]
    supported = {"epub", "docx", "txt", "html", "markdown"}
    formats = [item.strip().lower() for item in value.split(",") if item.strip()]
    return [fmt for fmt in formats if fmt in supported] or ["epub"]


def parse_page_no(path: Path) -> int | None:
    stem = path.stem
    if stem == "summary":
        return None
    try:
        return int(stem.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def mime_type_for_export(fmt: str) -> str | None:
    return {
        "epub": "application/epub+zip",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "html": "text/html",
        "txt": "text/plain",
    }.get(fmt)
