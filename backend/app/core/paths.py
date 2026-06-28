from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
STORAGE_ROOT = BACKEND_ROOT / "storage"
TASKS_ROOT = STORAGE_ROOT / "tasks"
PADDLEX_CACHE_ROOT = STORAGE_ROOT / "paddlex_cache"


def project_relative(path: Path) -> str:
    path = path.resolve() if path.exists() else path
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def resolve_task_dir(task: str, storage_root: Path = TASKS_ROOT) -> Path:
    task_path = Path(task).expanduser()
    if task_path.exists():
        return task_path.resolve()
    return (storage_root / task).resolve()
