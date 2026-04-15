import streamlit as st

from admin_agent import (
    apply_reservation_decision,
    get_default_admin_config,
    get_interrupt_action,
    get_result_text,
    invoke_admin_agent,
    resume_admin_agent,
)
from fake_db import fake_db_instance
from mcp_client import check_mcp_server_health


st.set_page_config(page_title="Admin Approvals", page_icon="✅", layout="centered")
st.title("Admin Approvals")
st.caption("Review pending requests and approve or reject reservations.")

is_mcp_healthy, mcp_health_message = check_mcp_server_health()
if not is_mcp_healthy:
    st.error(f"Storage service warning: {mcp_health_message}")
    st.caption("Approvals can still update in-memory state, but persistent MCP write may fail.")
else:
    st.caption("Storage service: connected")

if "admin_thread_id" not in st.session_state:
    st.session_state.admin_thread_id = "admin-session"
if "admin_pending_action" not in st.session_state:
    st.session_state.admin_pending_action = None


config = get_default_admin_config()
config["configurable"]["thread_id"] = st.session_state.admin_thread_id


def _send_admin_command(command: str) -> tuple[str, bool]:
    """Invoke admin agent and surface interrupt for chat-level approval."""
    result = invoke_admin_agent(command, config)
    action = get_interrupt_action(result)

    if action:
        st.session_state.admin_pending_action = action
        return ("Action paused: approval required before tool execution.", True)

    return (get_result_text(result), False)


def _resume_pending_action(approve: bool) -> str:
    result = resume_admin_agent(config=config, approve=approve)
    next_action = get_interrupt_action(result)
    st.session_state.admin_pending_action = next_action
    return get_result_text(result)


pending = [
    (reservation_id, reservation)
    for reservation_id, reservation in fake_db_instance.items()
    if reservation.status == "pending"
]

st.subheader("Pending requests")

if not pending:
    st.info("No pending reservation requests.")
else:
    for reservation_id, reservation in pending:
        with st.container(border=True):
            st.markdown(f"**Reservation ID:** {reservation_id}")
            st.write(f"Name: {reservation.full_name or '-'}")
            st.write(f"Plate: {reservation.numplate or '-'}")
            st.write(f"Start: {reservation.datetime_start}")
            st.write(f"End: {reservation.datetime_end}")

            note_key = f"note_{reservation_id}"
            decision_note = st.text_input("Decision note (optional)", key=note_key)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve", key=f"approve_{reservation_id}"):
                    output = apply_reservation_decision(
                        reservation_id=reservation_id,
                        status="approved",
                        note=decision_note.strip(),
                    )
                    st.success(output)
                    st.rerun()
            with col2:
                if st.button("Reject", key=f"reject_{reservation_id}"):
                    output = apply_reservation_decision(
                        reservation_id=reservation_id,
                        status="rejected",
                        note=decision_note.strip(),
                    )
                    st.warning(output)
                    st.rerun()


st.subheader("Admin assistant")
st.caption("Optional natural-language commands. Example: Show all reservations.")

if "admin_agent_history" not in st.session_state:
    st.session_state.admin_agent_history = []

for item in st.session_state.admin_agent_history[-10:]:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])

pending_action = st.session_state.admin_pending_action

if pending_action:
    with st.chat_message("assistant"):
        st.warning("Pending tool call requires confirmation")
        st.write(f"Tool: {pending_action.get('name', '-')}")
        st.json(pending_action.get("arguments", {}))

        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Execute tool call", key="approve_pending_tool"):
                output = _resume_pending_action(approve=True)
                st.success(output)
                st.rerun()
        with cancel_col:
            if st.button("Reject tool call", key="reject_pending_tool"):
                output = _resume_pending_action(approve=False)
                st.info(output)
                st.rerun()

admin_input = st.chat_input("Type an admin command...")
if admin_input:
    st.session_state.admin_agent_history.append({"role": "user", "content": admin_input})
    output, interrupted = _send_admin_command(admin_input)
    if interrupted:
        output = f"{output} Confirm or reject below this message."
    st.session_state.admin_agent_history.append({"role": "assistant", "content": output})
    st.rerun()
