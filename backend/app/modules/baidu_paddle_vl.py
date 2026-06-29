#!/usr/bin/env python3
"""Baidu PaddleOCR-VL cloud parser and project JSON adapter."""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
SUBMIT_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task"
QUERY_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task/query"

NOISE_TYPES = {"header", "footer", "number", "header_image", "footer_image"}


@dataclass(frozen=True)
class BaiduPaddleVlOptions:
    api_key: str | None = None
    secret_key: str | None = None
    access_token: str | None = None
    poll_interval: int = 8
    timeout_seconds: int = 900
    http_timeout: int = 60
    analysis_chart: bool = True
    merge_tables: bool = True
    relevel_titles: bool = True
    recognize_seal: bool = True
    return_span_boxes: bool = True


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def options_from_env(
    *,
    poll_interval: int = 8,
    timeout_seconds: int = 900,
    http_timeout: int = 60,
) -> BaiduPaddleVlOptions:
    return BaiduPaddleVlOptions(
        api_key=os.environ.get("BAIDU_OCR_API_KEY"),
        secret_key=os.environ.get("BAIDU_OCR_SECRET_KEY"),
        access_token=os.environ.get("BAIDU_OCR_ACCESS_TOKEN"),
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
        http_timeout=http_timeout,
    )


def run_baidu_paddle_vl(
    *,
    input_path: Path,
    task_dir: Path,
    options: BaiduPaddleVlOptions | None = None,
    file_name: str | None = None,
    file_url: str | None = None,
    input_file: str | None = None,
) -> dict[str, Any]:
    options = options or options_from_env()
    parse_result = fetch_cloud_result(
        input_path=input_path,
        task_dir=task_dir,
        options=options,
        file_name=file_name or input_path.name,
        file_url=file_url,
    )
    return convert_baidu_result(parse_result=parse_result, task_dir=task_dir, input_file=input_file)


def convert_baidu_parse_result_file(*, raw_json_path: Path, task_dir: Path, input_file: str | None = None) -> dict[str, Any]:
    parse_result = load_json(raw_json_path)
    write_json(task_dir / "cloud" / "baidu_parse_result.json", parse_result)
    return convert_baidu_result(parse_result=parse_result, task_dir=task_dir, input_file=input_file)


def fetch_cloud_result(
    *,
    input_path: Path,
    task_dir: Path,
    options: BaiduPaddleVlOptions,
    file_name: str,
    file_url: str | None = None,
) -> dict[str, Any]:
    cloud_dir = task_dir / "cloud"
    cloud_dir.mkdir(parents=True, exist_ok=True)
    access_token = resolve_access_token(options)

    submit_response = submit_task(input_path=input_path, file_name=file_name, file_url=file_url, access_token=access_token, options=options)
    write_json(cloud_dir / "baidu_submit_response.json", redact_token_info(submit_response))
    task_id = extract_submit_task_id(submit_response)
    print(f"[baidu] submitted task: {task_id}")

    query_response = wait_for_result(task_id=task_id, access_token=access_token, options=options)
    write_json(cloud_dir / "baidu_query_response.json", redact_token_info(query_response))
    result = query_response.get("result") or {}

    parse_result_url = result.get("parse_result_url")
    if not parse_result_url:
        raise RuntimeError(f"Query response does not contain parse_result_url: {query_response}")
    parse_result = json.loads(download_bytes(str(parse_result_url), timeout=options.http_timeout).decode("utf-8"))
    write_json(cloud_dir / "baidu_parse_result.json", parse_result)

    markdown_url = result.get("markdown_url")
    if markdown_url:
        (cloud_dir / "baidu_result.md").write_bytes(download_bytes(str(markdown_url), timeout=options.http_timeout))

    return parse_result


def resolve_access_token(options: BaiduPaddleVlOptions) -> str:
    if options.access_token:
        return options.access_token
    if not options.api_key or not options.secret_key:
        raise RuntimeError("Missing Baidu OCR credentials. Set BAIDU_OCR_ACCESS_TOKEN or BAIDU_OCR_API_KEY/BAIDU_OCR_SECRET_KEY.")
    return get_access_token(api_key=options.api_key, secret_key=options.secret_key, timeout=options.http_timeout)


def get_access_token(api_key: str, secret_key: str, timeout: int) -> str:
    data = http_post_form(
        TOKEN_URL,
        {"grant_type": "client_credentials", "client_id": api_key, "client_secret": secret_key},
        timeout=timeout,
    )
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"Token response does not contain access_token: {data}")
    return str(token)


def submit_task(
    *,
    input_path: Path,
    file_name: str,
    file_url: str | None,
    access_token: str,
    options: BaiduPaddleVlOptions,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "file_name": file_name,
        "analysis_chart": str(options.analysis_chart).lower(),
        "merge_tables": str(options.merge_tables).lower(),
        "relevel_titles": str(options.relevel_titles).lower(),
        "recognize_seal": str(options.recognize_seal).lower(),
        "return_span_boxes": str(options.return_span_boxes).lower(),
    }
    if file_url:
        payload["file_url"] = file_url
    else:
        payload["file_data"] = base64.b64encode(input_path.read_bytes()).decode("ascii")
    submit_url = f"{SUBMIT_URL}?{urllib.parse.urlencode({'access_token': access_token})}"
    return http_post_form(submit_url, payload, timeout=options.http_timeout)


def wait_for_result(*, task_id: str, access_token: str, options: BaiduPaddleVlOptions) -> dict[str, Any]:
    deadline = time.monotonic() + options.timeout_seconds
    last_response: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        response = query_task(task_id=task_id, access_token=access_token, timeout=options.http_timeout)
        last_response = response
        result = response.get("result") or {}
        status = str(result.get("status", "")).lower()
        print(f"[baidu] task={task_id}, status={status or 'unknown'}")
        if status == "success":
            return response
        if status == "failed":
            raise RuntimeError(f"Baidu task failed: {result.get('task_error') or response}")
        time.sleep(options.poll_interval)
    raise TimeoutError(f"Baidu task did not finish in {options.timeout_seconds}s: {last_response}")


def query_task(*, task_id: str, access_token: str, timeout: int) -> dict[str, Any]:
    query_url = f"{QUERY_URL}?{urllib.parse.urlencode({'access_token': access_token})}"
    return http_post_form(query_url, {"task_id": task_id}, timeout=timeout)


def http_post_form(url: str, data: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return read_json_response(request, timeout=timeout)


def read_json_response(request: urllib.request.Request, timeout: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network request failed: {exc}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Response is not JSON: {body[:500]}") from exc
    if data.get("error_code"):
        raise RuntimeError(f"Baidu API error {data.get('error_code')}: {data.get('error_msg')}")
    return data


def download_bytes(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Download failed, HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Download failed: {exc}") from exc


def extract_submit_task_id(response: dict[str, Any]) -> str:
    result = response.get("result") or {}
    task_id = result.get("task_id")
    if not task_id:
        raise RuntimeError(f"Submit response does not contain task_id: {response}")
    return str(task_id)


def redact_token_info(data: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(data, ensure_ascii=False)
    for key in ("access_token", "client_secret", "client_id"):
        text = text.replace(key, f"{key}_redacted")
    return json.loads(text)


def convert_baidu_result(parse_result: dict[str, Any], task_dir: Path, input_file: str | None) -> dict[str, Any]:
    started_at = datetime.now()
    pages = list(parse_result.get("pages") or [])
    page_outputs: list[dict[str, Any]] = []
    layout_summaries: list[dict[str, Any]] = []
    ocr_summaries: list[dict[str, Any]] = []

    for page_index, page in enumerate(pages, start=1):
        page_no = page_index
        layout_page, ocr_page = convert_page(parse_result, page, page_no, task_dir)
        write_json(task_dir / "layout" / f"page_{page_no:03d}.json", layout_page)
        write_json(task_dir / "ocr" / f"page_{page_no:03d}.json", ocr_page)
        page_outputs.append({"layout": layout_page, "ocr": ocr_page})
        layout_summaries.append(
            {
                "page_no": page_no,
                "layout_path": project_relative(task_dir / "layout" / f"page_{page_no:03d}.json"),
                "block_count": len(layout_page["blocks"]),
                "role_counts": count_by_key(layout_page["blocks"], "role"),
            }
        )
        ocr_summaries.append(
            {
                "page_no": page_no,
                "ocr_path": project_relative(task_dir / "ocr" / f"page_{page_no:03d}.json"),
                "ocr_block_count": ocr_page["ocr_block_count"],
                "recognized_block_count": ocr_page["recognized_block_count"],
                "line_count": ocr_page["line_count"],
            }
        )

    metadata = merge_metadata(
        task_dir,
        {
            "task_id": task_dir.name,
            "input_file": input_file,
            "provider": "baidu_paddle_vl",
            "source_file_name": parse_result.get("file_name"),
            "source_file_id": parse_result.get("file_id"),
            "cloud_converted_at": started_at.isoformat(timespec="seconds"),
            "page_count": len(pages),
        },
    )

    layout_summary = {
        "task_id": task_dir.name,
        "task_dir": project_relative(task_dir),
        "stage": "layout",
        "provider": "baidu_paddle_vl",
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "page_count": len(pages),
        "total_blocks": sum(item["block_count"] for item in layout_summaries),
        "pages": layout_summaries,
    }
    write_json(task_dir / "layout" / "summary.json", layout_summary)

    ocr_summary = {
        "task_id": task_dir.name,
        "task_dir": project_relative(task_dir),
        "stage": "ocr",
        "provider": "baidu_paddle_vl",
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "page_count": len(pages),
        "ocr_block_count": sum(item["ocr_block_count"] for item in ocr_summaries),
        "recognized_block_count": sum(item["recognized_block_count"] for item in ocr_summaries),
        "empty_block_count": sum(page["ocr"]["ocr_block_count"] - page["ocr"]["recognized_block_count"] for page in page_outputs),
        "skipped_block_count": sum(page["ocr"]["skipped_block_count"] for page in page_outputs),
        "line_count": sum(item["line_count"] for item in ocr_summaries),
        "avg_confidence": None,
        "pages": ocr_summaries,
    }
    write_json(task_dir / "ocr" / "summary.json", ocr_summary)
    return {"metadata": metadata, "layout_summary": layout_summary, "ocr_summary": ocr_summary}


def merge_metadata(task_dir: Path, updates: dict[str, Any]) -> dict[str, Any]:
    metadata_path = task_dir / "metadata.json"
    metadata = load_json(metadata_path) if metadata_path.exists() else {}
    metadata.update({key: value for key, value in updates.items() if value is not None})
    write_json(metadata_path, metadata)
    return metadata


def convert_page(parse_result: dict[str, Any], page: dict[str, Any], page_no: int, task_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    meta = page.get("meta") or {}
    source_page_num = page.get("page_num")
    width = safe_number(meta.get("page_width"))
    height = safe_number(meta.get("page_height"))
    tables = {str(item.get("layout_id")): item for item in page.get("tables") or []}
    images = {str(item.get("layout_id")): item for item in page.get("images") or []}
    blocks: list[dict[str, Any]] = []
    skipped_blocks: list[dict[str, Any]] = []

    for index, layout in enumerate(page.get("layouts") or [], start=1):
        block_id = f"p{page_no:03d}_b{index:04d}"
        raw_type = str(layout.get("type") or "unknown")
        role, reading_group, is_noise = map_layout_type(raw_type)
        text = text_for_layout(layout, tables, images)
        bbox = position_to_bbox(layout.get("position"))
        lines = lines_for_layout(layout, bbox)
        if text and not lines:
            lines = [{"line_no": 1, "text": text, "confidence": None, "bbox": bbox, "polygon": []}]

        layout_block = {
            "block_id": block_id,
            "source": "baidu_paddle_vl",
            "raw_id": layout.get("layout_id"),
            "raw_type": raw_type,
            "role": role,
            "bbox": bbox,
            "confidence": {"detector": None, "rule": None, "final": None},
            "column": None,
            "order": index if not is_noise else None,
            "reading_group": reading_group,
            "is_noise": is_noise,
            "notes": ["converted_from_baidu_paddle_vl"],
            "baidu": compact_baidu_layout(layout, tables, images),
        }
        blocks.append(layout_block)
        if is_noise:
            skipped_blocks.append({"block_id": block_id, "role": role, "reading_group": reading_group, "reason": f"skip_role:{role}"})

    layout_page = {
        "task_id": task_dir.name,
        "page_no": page_no,
        "image_path": "",
        "width": width,
        "height": height,
        "page_type": "baidu_document",
        "layout_type": "baidu_reading_order",
        "provider": "baidu_paddle_vl",
        "baidu_page_num": source_page_num,
        "source_file_name": parse_result.get("file_name"),
        "blocks": blocks,
    }

    ocr_blocks = []
    for block in blocks:
        if block["is_noise"]:
            continue
        lines = lines_for_layout_by_id(page, block.get("raw_id"), block["bbox"])
        ocr_blocks.append(
            {
                "block_id": block["block_id"],
                "page_no": page_no,
                "role": block["role"],
                "raw_type": block["raw_type"],
                "text": text_for_layout_by_id(page, block.get("raw_id")),
                "ocr_confidence": None,
                "bbox": block["bbox"],
                "column": block.get("column"),
                "order": block.get("order"),
                "reading_group": block.get("reading_group"),
                "layout_confidence": None,
                "line_count": len(lines),
                "lines": lines,
                "crop_path": None,
                "timing": None,
                "is_noise": block["is_noise"],
                "baidu_layout_id": block.get("raw_id"),
            }
        )
    recognized_blocks = [block for block in ocr_blocks if str(block.get("text") or "").strip()]
    ocr_page = {
        "task_id": task_dir.name,
        "page_no": page_no,
        "image_path": "",
        "page_type": "baidu_document",
        "layout_type": "baidu_reading_order",
        "provider": "baidu_paddle_vl",
        "baidu_page_num": source_page_num,
        "ocr_seconds": None,
        "ocr_block_count": len(ocr_blocks),
        "recognized_block_count": len(recognized_blocks),
        "skipped_block_count": len(skipped_blocks),
        "line_count": sum(block["line_count"] for block in ocr_blocks),
        "avg_confidence": None,
        "blocks": ocr_blocks,
        "skipped_blocks": skipped_blocks,
    }
    return layout_page, ocr_page


def map_layout_type(raw_type: str) -> tuple[str, str, bool]:
    normalized = raw_type.strip().lower()
    if normalized in NOISE_TYPES:
        return normalized if normalized != "number" else "page_number", "noise", True
    mapping = {
        "doc_title": ("title", "main"),
        "paragraph_title": ("subtitle", "main"),
        "figure_title": ("caption", "caption"),
        "table_title": ("caption", "caption"),
        "abstract": ("body", "main"),
        "algorithm": ("body", "main"),
        "aside_text": ("sidebar", "main"),
        "content": ("body", "main"),
        "footnote": ("note", "main"),
        "reference": ("body", "main"),
        "reference_content": ("body", "main"),
        "text": ("body", "main"),
        "vertical_text": ("body", "main"),
        "table": ("table", "visual"),
        "image": ("figure", "visual"),
        "chart": ("figure", "visual"),
        "seal": ("figure", "visual"),
        "display_formula": ("formula", "visual"),
        "inline_formula": ("formula", "visual"),
        "formula_number": ("formula", "visual"),
    }
    role, reading_group = mapping.get(normalized, ("body", "main"))
    return role, reading_group, False


def text_for_layout(layout: dict[str, Any], tables: dict[str, dict[str, Any]], images: dict[str, dict[str, Any]]) -> str:
    layout_id = str(layout.get("layout_id"))
    raw_type = str(layout.get("type") or "").lower()
    if raw_type == "table":
        table = tables.get(layout_id) or {}
        return str(table.get("markdown") or layout.get("text") or "").strip()
    if raw_type in {"image", "chart"}:
        image = images.get(layout_id) or {}
        return normalize_image_description(image.get("image_description")) or str(layout.get("text") or "").strip()
    return str(layout.get("text") or "").strip()


def normalize_image_description(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value.strip()
        return json.dumps(parsed, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


def text_for_layout_by_id(page: dict[str, Any], layout_id: Any) -> str:
    tables = {str(item.get("layout_id")): item for item in page.get("tables") or []}
    images = {str(item.get("layout_id")): item for item in page.get("images") or []}
    for layout in page.get("layouts") or []:
        if str(layout.get("layout_id")) == str(layout_id):
            return text_for_layout(layout, tables, images)
    return ""


def lines_for_layout_by_id(page: dict[str, Any], layout_id: Any, fallback_bbox: dict[str, float]) -> list[dict[str, Any]]:
    for layout in page.get("layouts") or []:
        if str(layout.get("layout_id")) == str(layout_id):
            return lines_for_layout(layout, fallback_bbox)
    return []


def lines_for_layout(layout: dict[str, Any], fallback_bbox: dict[str, float]) -> list[dict[str, Any]]:
    lines = []
    for index, span in enumerate(layout.get("span_boxes") or [], start=1):
        text = span.get("text", "")
        if isinstance(text, list):
            text = "".join(str(item) for item in text)
        location = span.get("location") or span.get("position")
        lines.append(
            {
                "line_no": index,
                "text": str(text),
                "confidence": None,
                "bbox": position_to_bbox(location) if location else fallback_bbox,
                "polygon": [],
            }
        )
    return lines


def compact_baidu_layout(layout: dict[str, Any], tables: dict[str, dict[str, Any]], images: dict[str, dict[str, Any]]) -> dict[str, Any]:
    layout_id = str(layout.get("layout_id"))
    data = {"layout_id": layout.get("layout_id"), "type": layout.get("type"), "sub_type": layout.get("sub_type"), "polygon": layout.get("polygon")}
    if layout_id in tables:
        data["table"] = tables[layout_id]
    if layout_id in images:
        data["image"] = images[layout_id]
    return data


def position_to_bbox(position: Any) -> dict[str, float]:
    if not position or len(position) < 4:
        return {"x1": 0.0, "y1": 0.0, "x2": 0.0, "y2": 0.0}
    x, y, w, h = [safe_number(item) for item in position[:4]]
    return {"x1": round4(x), "y1": round4(y), "x2": round4(x + w), "y2": round4(y + h)}


def safe_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round4(value: float) -> float:
    return round(float(value), 4)


def count_by_key(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts
