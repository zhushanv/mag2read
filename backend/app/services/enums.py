from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TaskStage(str, Enum):
    RENDER = "render"
    LAYOUT_DETECT = "layout_detect"
    LAYOUT_REFINE = "layout_refine"
    OCR = "ocr"
    TEXT_CLEANING = "text_cleaning"
    DOCUMENT_BUILD = "document_build"
    EXPORT = "export"
    AI_READING = "ai_reading"


class InputType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    IMAGE_DIRECTORY = "image_directory"
