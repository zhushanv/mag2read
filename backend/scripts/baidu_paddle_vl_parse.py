#!/usr/bin/env python3
"""Command-line wrapper for Baidu PaddleOCR-VL cloud parsing."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.modules.baidu_paddle_vl import (
    BaiduPaddleVlOptions,
    convert_baidu_parse_result_file,
    project_relative,
    run_baidu_paddle_vl,
)


DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "backend" / "storage" / "tasks"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def create_task_dir(args: argparse.Namespace) -> Path:
    if args.output_task_dir:
        task_dir = Path(args.output_task_dir).expanduser().resolve()
    else:
        task_id = args.task_id or build_local_task_id(args.input, args.raw_json)
        task_dir = Path(args.storage_root).expanduser().resolve() / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def build_local_task_id(input_path: str | None, raw_json: str | None) -> str:
    source = Path(input_path or raw_json or "baidu_document").stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_source = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in source).strip("_")
    return f"baidu_{safe_source or 'document'}_{timestamp}"


def save_input_file(args: argparse.Namespace, task_dir: Path) -> str | None:
    if args.file_url or args.raw_json or not args.input:
        return None
    input_path = Path(args.input).expanduser().resolve()
    target = task_dir / "input" / input_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if input_path != target:
        shutil.copy2(input_path, target)
    return project_relative(target)


def build_options(args: argparse.Namespace) -> BaiduPaddleVlOptions:
    return BaiduPaddleVlOptions(
        api_key=os.environ.get(args.api_key_env),
        secret_key=os.environ.get(args.secret_key_env),
        access_token=os.environ.get(args.access_token_env),
        poll_interval=args.poll_interval,
        timeout_seconds=args.timeout_seconds,
        http_timeout=args.http_timeout,
        analysis_chart=args.analysis_chart,
        merge_tables=args.merge_tables,
        relevel_titles=args.relevel_titles,
        recognize_seal=args.recognize_seal,
        return_span_boxes=args.return_span_boxes,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="提交单个文件到百度文档解析（PaddleOCR-VL），并转换为本项目 layout/ocr JSON。"
    )
    parser.add_argument("input", nargs="?", help="本地 PDF/图片/文档路径。使用 --raw-json 时可省略。")
    parser.add_argument("--raw-json", help="跳过云端调用，直接把已有百度 parse_result JSON 转换为项目格式。")
    parser.add_argument("--file-url", help="使用可公网访问的文件 URL 提交。大文件建议使用该方式。")
    parser.add_argument("--file-name", help="提交给百度的文件名；默认使用 input 文件名。")
    parser.add_argument("--task-id", help="本地输出任务 ID；默认按 baidu_{文件名}_{时间} 生成。")
    parser.add_argument("--output-task-dir", help="完整输出目录；设置后优先于 --storage-root 和 --task-id。")
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT), help="任务存储根目录。")
    parser.add_argument("--dotenv", default=str(PROJECT_ROOT / ".env"), help="可选 .env 路径。")
    parser.add_argument("--api-key-env", default="BAIDU_OCR_API_KEY", help="API Key 环境变量名。")
    parser.add_argument("--secret-key-env", default="BAIDU_OCR_SECRET_KEY", help="Secret Key 环境变量名。")
    parser.add_argument("--access-token-env", default="BAIDU_OCR_ACCESS_TOKEN", help="Access Token 环境变量名。")
    parser.add_argument("--poll-interval", type=int, default=8, help="任务查询间隔秒数，官方建议 5 到 10 秒。")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="等待云端任务完成的最长秒数。")
    parser.add_argument("--http-timeout", type=int, default=60, help="单次 HTTP 请求超时秒数。")
    parser.add_argument("--analysis-chart", action=argparse.BooleanOptionalAction, default=True, help="是否解析统计图表。")
    parser.add_argument("--merge-tables", action=argparse.BooleanOptionalAction, default=True, help="是否合并跨页表格。")
    parser.add_argument("--relevel-titles", action=argparse.BooleanOptionalAction, default=True, help="是否输出标题层级。")
    parser.add_argument("--recognize-seal", action=argparse.BooleanOptionalAction, default=True, help="是否识别印章。")
    parser.add_argument("--return-span-boxes", action=argparse.BooleanOptionalAction, default=True, help="是否返回行坐标。")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.raw_json:
        if not Path(args.raw_json).expanduser().exists():
            raise FileNotFoundError(f"raw json does not exist: {args.raw_json}")
        return
    if not args.input and not args.file_url:
        raise ValueError("需要提供 input 本地文件，或提供 --file-url。")
    if args.input and not Path(args.input).expanduser().exists():
        raise FileNotFoundError(f"input file does not exist: {args.input}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        load_dotenv(Path(args.dotenv).expanduser())
        validate_args(args)
        task_dir = create_task_dir(args)
        input_file = save_input_file(args, task_dir)
        if args.raw_json:
            outputs = convert_baidu_parse_result_file(
                raw_json_path=Path(args.raw_json).expanduser().resolve(),
                task_dir=task_dir,
                input_file=input_file,
            )
        else:
            input_path = Path(args.input).expanduser().resolve() if args.input else Path(args.file_name or "document.pdf")
            outputs = run_baidu_paddle_vl(
                input_path=input_path,
                task_dir=task_dir,
                options=build_options(args),
                file_name=args.file_name or input_path.name,
                file_url=args.file_url,
                input_file=input_file,
            )
    except Exception as exc:
        print(f"百度文档解析失败: {exc}")
        return 1

    print("百度文档解析完成")
    print(f"Task dir: {project_relative(task_dir)}")
    print(f"Pages: {outputs['metadata']['page_count']}")
    print(f"Layout summary: {outputs['layout_summary']['task_dir']}/layout/summary.json")
    print(f"OCR summary: {outputs['ocr_summary']['task_dir']}/ocr/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
