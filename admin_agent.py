"""Admin-facing LangChain agent with HITL interrupts for reservation approvals."""

from dataclasses import replace
from datetime import datetime as dt
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from fake_db import fake_db_instance, debug_print_fake_db


def _fmt_datetime(value: dt | None) -> str:
    if not value:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


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
                    _fmt_datetime(reservation.datetime_start),
                    _fmt_datetime(reservation.datetime_end),
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


ADMIN_TOOLS = [get_reservations, update_reservation_status]
_ADMIN_MODEL = ChatOpenAI(model="gpt-5-mini", temperature=0)

_ADMIN_SYSTEM_PROMPT = """You are an administrator assistant for Skyline Belgrade Parking reservations.

Your job:
1. Show reservations when asked.
2. Approve or reject reservations by id.

Rules:
- Use get_reservations when admin asks to list requests.
- Use update_reservation_status only with status 'approved' or 'rejected'.
- Never invent reservation IDs.
- If ID is missing or unclear, ask a short clarification.
"""


admin_agent = create_agent(
    model=_ADMIN_MODEL,
    tools=ADMIN_TOOLS,
    system_prompt=_ADMIN_SYSTEM_PROMPT,
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "update_reservation_status": True,
                "get_reservations": False,
            }
        )
    ],
    checkpointer=InMemorySaver(),
)


def get_default_admin_config() -> dict:
    return {"configurable": {"thread_id": "admin-session"}}


def invoke_admin_agent(user_input: str, config: dict | None = None):
    cfg = config or get_default_admin_config()
    payload = {"messages": [{"role": "user", "content": user_input}]}
    return admin_agent.invoke(payload, config=cfg, version="v2")

def _extract_interrupts(result) -> list:
    interrupts = getattr(result, "interrupts", None)
    if interrupts is None and isinstance(result, dict):
        interrupts = result.get("interrupts")
    return interrupts or []

def get_interrupt_action(result) -> dict | None:
    interrupts = _extract_interrupts(result)
    if not interrupts:
        return None

    first = interrupts[0]
    payload = getattr(first, "value", first)
    if not isinstance(payload, dict):
        return None

    actions = payload.get("action_requests") or []
    if not actions:
        return None

    return actions[0]


def get_result_text(result) -> str:
    try:
        messages = result["messages"]
        return messages[-1].content
    except Exception:
        return str(result)


def resume_admin_agent(config: dict | None = None, approve: bool = True):
    cfg = config or get_default_admin_config()
    decision_type = "approve" if approve else "reject"
    resume_cmd = Command(resume={"decisions": [{"type": decision_type}]})
    return admin_agent.invoke(resume_cmd, config=cfg, version="v2")


if __name__ == "__main__":
    print("Admin agent started. Type 'exit' to quit.")
    config = get_default_admin_config()

    while True:
        user_input = input("Admin: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        result = invoke_admin_agent(user_input, config)
        action = get_interrupt_action(result)

        if action:
            print("\nACTION REQUIRES APPROVAL")
            print(f"Tool: {action.get('name')}")
            print(f"Args: {action.get('arguments')}")
            decision = input("Approve / Reject: ").strip().lower()

            if decision == "approve":
                result = resume_admin_agent(config=config, approve=True)
            elif decision == "reject":
                result = resume_admin_agent(config=config, approve=False)
            else:
                print("Skipped (invalid decision).\n")
                continue

        print(f"\nAgent: {get_result_text(result)}\n")
