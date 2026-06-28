from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.core.paths import PADDLEX_CACHE_ROOT, TASKS_ROOT, resolve_task_dir
from backend.app.modules.document_build import build_document, write_outputs
from backend.app.modules.export_document import run_export
from backend.app.modules.layout_detect import analyze_task_layout
from backend.app.modules.layout_refine import refine_task_layout
from backend.app.modules.ocr import run_task_ocr
from backend.app.modules.render import build_task_id, render_input_pages
from backend.app.modules.text_cleaning import run_cleaning


@dataclass
class PipelineConfig:
    storage_root: Path = TASKS_ROOT
    paddlex_cache: Path = PADDLEX_CACHE_ROOT
    dpi: int = 200
    page_range: str | None = None
    overwrite: bool = False
    copy_input: bool = True
    layout_threshold: float | None = None
    draw_layout_debug: bool = True
    ocr_padding: int = 4
    include_unknown_ocr: bool = False
    save_ocr_crops: bool = False
    use_textline_orientation: bool = False
    export_formats: list[str] = field(default_factory=lambda: ["epub"])


def create_task_from_input(
    input_path: Path,
    task_id: str | None = None,
    config: PipelineConfig | None = None,
) -> dict[str, Any]:
    config = config or PipelineConfig()
    task_name = build_task_id(task_id)
    task_dir = config.storage_root / task_name
    return render_input_pages(
        input_path=input_path.expanduser().resolve(),
        task_dir=task_dir,
        dpi=config.dpi,
        page_range=config.page_range,
        overwrite=config.overwrite,
        copy_input=config.copy_input,
    )


def run_stage(task: str, stage: str, config: PipelineConfig | None = None) -> Any:
    config = config or PipelineConfig()
    task_dir = resolve_task_dir(task, config.storage_root)

    if stage == "layout_detect":
        return analyze_task_layout(
            task_dir=task_dir,
            cache_dir=config.paddlex_cache,
            threshold=config.layout_threshold,
            draw_debug=config.draw_layout_debug,
        )
    if stage == "layout_refine":
        return refine_task_layout(task_dir)
    if stage == "ocr":
        return run_task_ocr(
            task_dir=task_dir,
            cache_dir=config.paddlex_cache,
            padding=config.ocr_padding,
            include_unknown=config.include_unknown_ocr,
            save_crops=config.save_ocr_crops,
            use_textline_orientation=config.use_textline_orientation,
        )
    if stage == "text_cleaning":
        return run_cleaning(task_dir)
    if stage == "document_build":
        document = build_document(task_dir)
        return write_outputs(task_dir, document)
    if stage == "export":
        return run_export(task_dir, config.export_formats)

    raise ValueError(f"Unknown pipeline stage: {stage}")


def run_existing_task(
    task: str,
    stages: list[str] | None = None,
    config: PipelineConfig | None = None,
) -> dict[str, Any]:
    selected_stages = stages or ["layout_detect", "layout_refine", "ocr", "text_cleaning", "document_build"]
    results: dict[str, Any] = {}
    for stage in selected_stages:
        results[stage] = run_stage(task, stage, config=config)
    return results


def run_full_pipeline(
    input_path: Path,
    task_id: str | None = None,
    config: PipelineConfig | None = None,
    stages_after_render: list[str] | None = None,
) -> dict[str, Any]:
    config = config or PipelineConfig()
    render_metadata = create_task_from_input(input_path, task_id=task_id, config=config)
    task = str(render_metadata["task_id"])
    results = {"render": render_metadata}
    results.update(run_existing_task(task, stages=stages_after_render, config=config))
    return results
