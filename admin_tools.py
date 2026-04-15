"""Admin tool functions for reservation review and decision workflows."""

from dataclasses import replace
from datetime import datetime as dt
from typing import Literal

from langchain.tools import tool

from fake_db import debug_print_fake_db, fake_db_instance


def _format_datetime(value: dt | None) -> str:
    if not value:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


def apply_reservation_decision(
    reservation_id: str,
    status: Literal["approved", "rejected"],
    note: str = "",
) -> str:
    reservation = fake_db_instance.get(reservation_id)
    if reservation is None:
        return f"Reservation {reservation_id} not found."

    now = dt.now()
    fake_db_instance[reservation_id] = replace(
        reservation,
        status=status,
        escalated_to_admin=True,
        escalated_at=reservation.escalated_at or now,
        decided_at=now,
        decision_note=note,
        updated_at=now,
    )
    debug_print_fake_db(f"[fake_db:admin_{status}]")

    return f"Reservation {reservation_id} updated to {status}."


@tool
def get_reservations(status: Literal["pending", "approved", "rejected", "all"] = "pending") -> str:
    """List reservations filtered by status. Use status='all' to show everything."""
    rows: list[tuple[str, object]] = []

    for reservation_id, reservation in fake_db_instance.items():
        if status != "all" and reservation.status != status:
            continue
        rows.append((reservation_id, reservation))

    if not rows:
        if status == "all":
            return "No reservations found."
        return f"No {status} reservations found."

    rows.sort(key=lambda item: item[1].updated_at, reverse=True)

    lines = []
    for reservation_id, reservation in rows:
        lines.append(
            " | ".join(
                [
                    reservation_id,
                    reservation.full_name or "-",
                    reservation.numplate or "-",
                    _format_datetime(reservation.datetime_start),
                    _format_datetime(reservation.datetime_end),
                    reservation.status,
                    f"escalated={reservation.escalated_to_admin}",
                ]
            )
        )

    header = "reservation_id | name | plate | start | end | status | escalated"
    return "\n".join([header, *lines])


@tool
def update_reservation_status(
    reservation_id: str,
    status: Literal["approved", "rejected"],
    note: str = "",
) -> str:
    """Approve or reject a reservation by reservation_id."""
    return apply_reservation_decision(reservation_id=reservation_id, status=status, note=note)
