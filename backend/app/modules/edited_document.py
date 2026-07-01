"""Manage manually edited task documents."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_document_path(task_dir: Path) -> Path:
    return task_dir / "clean" / "document.json"


def edited_document_path(task_dir: Path) -> Path:
    return task_dir / "edited" / "document.json"


def document_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_editable_document(task_dir: Path) -> dict[str, Any]:
    edited_path = edited_document_path(task_dir)
    clean_path = clean_document_path(task_dir)

    if edited_path.exists():
        document = read_json(edited_path)
        return {
            "task_id": task_dir.name,
            "source": "edited",
            "has_edited": True,
            "document_path": project_relative(edited_path),
            "base_document_path": project_relative(clean_path),
            "document": document,
            "manual_edit": document.get("manual_edit"),
        }

    if not clean_path.exists():
        raise FileNotFoundError("clean/document.json does not exist")

    document = read_json(clean_path)
    return {
        "task_id": task_dir.name,
        "source": "clean",
        "has_edited": False,
        "document_path": project_relative(clean_path),
        "base_document_path": project_relative(clean_path),
        "document": document,
        "manual_edit": None,
    }


def load_export_document(task_dir: Path) -> dict[str, Any]:
    edited_path = edited_document_path(task_dir)
    if edited_path.exists():
        return read_json(edited_path)

    clean_path = clean_document_path(task_dir)
    if not clean_path.exists():
        raise FileNotFoundError("clean/document.json does not exist")
    return read_json(clean_path)


def extract_document_payload(payload: dict[str, Any]) -> dict[str, Any]:
    document = payload.get("document") if isinstance(payload.get("document"), dict) else payload
    if not isinstance(document, dict):
        raise ValueError("Edited document must be a JSON object")
    if not isinstance(document.get("pages"), list) and not isinstance(document.get("blocks"), list):
        raise ValueError("Edited document must contain pages or blocks")
    return dict(document)


def save_edited_document(task_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    clean_path = clean_document_path(task_dir)
    if not clean_path.exists():
        raise FileNotFoundError("clean/document.json does not exist")

    output_path = edited_document_path(task_dir)
    document = extract_document_payload(payload)
    previous = read_json(output_path) if output_path.exists() else {}
    previous_meta = previous.get("manual_edit") if isinstance(previous.get("manual_edit"), dict) else {}
    version = int(previous_meta.get("version") or 0) + 1
    edited_at = datetime.now().isoformat(timespec="seconds")

    document["task_id"] = str(document.get("task_id") or task_dir.name)
    document["manual_edit"] = {
        "source": "manual_edit",
        "version": version,
        "edited_at": edited_at,
        "base_document_path": project_relative(clean_path),
        "base_document_hash": document_hash(clean_path),
    }
    write_json(output_path, document)
    return load_editable_document(task_dir)


def reset_edited_document(task_dir: Path) -> dict[str, Any]:
    output_path = edited_document_path(task_dir)
    if output_path.exists():
        output_path.unlink()
    return load_editable_document(task_dir)
