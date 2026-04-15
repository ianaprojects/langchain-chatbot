"""MCP tools — reservation persistence."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from fastmcp import Context

from mcp_server.auth import require_authorized
from mcp_server.validation import (
    extract_required_text,
    normalize_optional_iso_datetime,
    sanitize_text,
    validate_iso_datetime,
)

_ROOT = Path(__file__).resolve().parent.parent
_FAKE_DB_APPROVED_RESERVATIONS_FILE = _ROOT / "fake_db_approved_reservations.jsonl"
_FILE_LOCK = threading.Lock()


def save_reservation(reservation: dict[str, Any], ctx: Context) -> str:
    """Persist one approved reservation from a fake_db-shaped payload."""
    require_authorized(ctx)
    return save_reservation_record(reservation=reservation)


def save_reservation_record(reservation: dict[str, Any]) -> str:
    """Append one approved reservation as a JSON line to the JSONL store."""
    if not isinstance(reservation, dict):
        raise ValueError("reservation payload must be an object")

    safe_status = extract_required_text(reservation, "status")
    if safe_status != "approved":
        raise ValueError("Only approved reservations can be persisted")

    payload = {
        "reservation_id": extract_required_text(reservation, "reservation_id"),
        "full_name": extract_required_text(reservation, "full_name"),
        "numplate": extract_required_text(reservation, "numplate"),
        "datetime_start": validate_iso_datetime(str(reservation.get("datetime_start", "")), "datetime_start"),
        "datetime_end": validate_iso_datetime(str(reservation.get("datetime_end", "")), "datetime_end"),
        "status": safe_status,
        "escalated_to_admin": bool(reservation.get("escalated_to_admin", False)),
        "escalated_at": normalize_optional_iso_datetime(
            reservation.get("escalated_at") if isinstance(reservation.get("escalated_at"), str) else None,
            "escalated_at",
        ),
        "decided_at": normalize_optional_iso_datetime(
            reservation.get("decided_at") if isinstance(reservation.get("decided_at"), str) else None,
            "decided_at",
        ),
        "decision_note": sanitize_text(str(reservation.get("decision_note", ""))),
        "created_at": validate_iso_datetime(str(reservation.get("created_at", "")), "created_at"),
        "updated_at": validate_iso_datetime(str(reservation.get("updated_at", "")), "updated_at"),
        "approval_time": datetime.now().isoformat(timespec="seconds"),
    }

    with _FILE_LOCK:
        with _FAKE_DB_APPROVED_RESERVATIONS_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    return "Reservation saved"
