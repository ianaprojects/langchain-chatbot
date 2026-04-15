"""MCP payload validation and input sanitization."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

_SAFE_TEXT_PATTERN = re.compile(r"[^a-zA-Z0-9 _\-.:()/,+@]")


def sanitize_text(value: str) -> str:
    """Whitelist expected characters and strip unsafe delimiters/newlines."""
    normalized = (value or "").replace("\n", " ").replace("\r", " ").replace("|", " ").strip()
    return _SAFE_TEXT_PATTERN.sub("", normalized)


def validate_iso_datetime(value: str, field_name: str) -> str:
    if not value:
        raise ValueError(f"{field_name} is required")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO datetime") from exc
    return value


def normalize_optional_iso_datetime(value: str | None, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    return validate_iso_datetime(value, field_name)


def extract_required_text(payload: dict[str, Any], key: str) -> str:
    raw = payload.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{key} is required")
    return sanitize_text(raw)
