from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, DECIMAL, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from backend.app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(32), nullable=False, default="user")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, unique=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    original_name = Column(String(255), nullable=False)
    input_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)
    current_stage = Column(String(64), nullable=True)
    progress = Column(Integer, nullable=False, default=0)
    storage_dir = Column(String(500), nullable=False)
    page_count = Column(Integer, nullable=True)
    output_format = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_created_at", "created_at"),
    )


class TaskFile(Base):
    __tablename__ = "task_files"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False, index=True)
    file_role = Column(String(64), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(128), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    page_no = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_task_files_role", "task_id", "file_role"),
        Index("idx_task_files_page", "task_id", "page_no"),
    )


class TaskPage(Base):
    __tablename__ = "task_pages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False, index=True)
    page_no = Column(Integer, nullable=False)
    image_path = Column(String(500), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    quality_status = Column(String(32), nullable=True)
    page_type = Column(String(64), nullable=True)
    layout_type = Column(String(64), nullable=True)
    ocr_status = Column(String(32), nullable=True)
    avg_confidence = Column(DECIMAL(5, 4), nullable=True)
    need_review = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("task_id", "page_no", name="uq_task_pages_task_page"),
        Index("idx_task_pages_review", "task_id", "need_review"),
        Index("idx_task_pages_type", "task_id", "page_type"),
    )


class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    summary_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("task_id", "stage", name="uq_task_steps_task_stage"),
        Index("idx_task_steps_status", "task_id", "status"),
    )


class ExportRecord(Base):
    __tablename__ = "export_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False, index=True)
    format = Column(String(32), nullable=False)
    file_path = Column(String(500), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    status = Column(String(32), nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_export_records_task_format", "task_id", "format"),
        Index("idx_export_records_status", "task_id", "status"),
    )
