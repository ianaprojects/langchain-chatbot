"""Stage 4 unified orchestration graph.

Pipeline:
1) User interaction via user_agent LangGraph
2) Escalation check for pending reservation state
3) Admin-stage invocation for review context

Approved reservation persistence remains in admin_tools.apply_reservation_decision,
which calls MCP via mcp_client. This keeps a single write path.
"""

from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from admin_agent import (
    get_default_admin_config,
    get_result_text,
    invoke_admin_agent,
)
from fake_db import fake_db_instance
from user_agent import user_agent


class OrchestratorState(TypedDict):
    messages: Annotated[list, add_messages]
    escalate_to_admin: bool
    admin_summary: str


def _find_latest_assistant(messages: list) -> AIMessage | None:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg
    return None


def _thread_id_from_config(config: RunnableConfig | None) -> str:
    if not config:
        return "user"
    configurable = config.get("configurable", {})
    return str(configurable.get("thread_id", "user"))


def should_escalate_to_admin(thread_id: str) -> bool:
    reservation = fake_db_instance.get(thread_id)
    if reservation is None:
        return False
    return reservation.status == "pending" and bool(reservation.escalated_to_admin)


def run_user_interaction_node(state: OrchestratorState, config: RunnableConfig | None = None):
    cfg = config or {"configurable": {"thread_id": "user"}}
    user_agent.invoke({"messages": state["messages"]}, config=cfg)
    snapshot = user_agent.get_state(cfg)
    assistant = _find_latest_assistant(snapshot.values.get("messages", []))

    if assistant is None:
        return {}

    # Keep only the final assistant turn from user stage in orchestrator history.
    return {"messages": [AIMessage(content=str(assistant.content))]}


def evaluate_escalation_node(state: OrchestratorState, config: RunnableConfig | None = None):
    thread_id = _thread_id_from_config(config)
    return {"escalate_to_admin": should_escalate_to_admin(thread_id)}


def route_after_escalation(state: OrchestratorState) -> Literal["admin_review", "done"]:
    if state.get("escalate_to_admin", False):
        return "admin_review"
    return "done"


def admin_review_node(state: OrchestratorState, config: RunnableConfig | None = None):
    thread_id = _thread_id_from_config(config)
    admin_cfg = get_default_admin_config()
    admin_cfg["configurable"]["thread_id"] = f"admin-{thread_id}"

    # The admin agent lists pending reservations so the HITL review context is
    # prepared in the second-agent thread without auto-approving anything.
    result = invoke_admin_agent("Show pending reservations.", config=admin_cfg)
    admin_summary = get_result_text(result)

    return {
        "admin_summary": admin_summary,
        "messages": [
            AIMessage(
                content=(
                    "Your reservation request was escalated to admin review. "
                    "An administrator will approve or reject it shortly."
                )
            )
        ],
    }


def create_master_orchestrator():
    graph = StateGraph(OrchestratorState)

    graph.add_node("user_interaction", run_user_interaction_node)
    graph.add_node("evaluate_escalation", evaluate_escalation_node)
    graph.add_node("admin_review", admin_review_node)

    graph.set_entry_point("user_interaction")
    graph.add_edge("user_interaction", "evaluate_escalation")
    graph.add_conditional_edges(
        "evaluate_escalation",
        route_after_escalation,
        {"admin_review": "admin_review", "done": END},
    )
    graph.add_edge("admin_review", END)

    return graph.compile(checkpointer=InMemorySaver())


master_orchestrator = create_master_orchestrator()
