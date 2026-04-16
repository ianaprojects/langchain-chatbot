"""Load checks with three required scenarios.

Scenarios:
1) Chatbot interactive dialogue mode (orchestrator invocation path)
2) Admin confirmation functionality (approve/reject decision path)
3) MCP recording and storage process (approval -> MCP save call path)

The script keeps execution deterministic by mocking model and network boundaries
while exercising project orchestration and admin logic.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import asdict
from datetime import datetime as dt
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import orchestrator
from admin_tools import apply_reservation_decision
from fake_db import ReservationData, fake_db_instance


def _summarize(name: str, latencies: list[float], errors: int, extra: dict | None = None) -> dict:
    if not latencies:
        latencies = [0.0]
    sorted_latencies = sorted(latencies)
    p95_index = max(0, int(len(sorted_latencies) * 0.95) - 1)
    summary = {
        "scenario": name,
        "iterations": len(latencies),
        "errors": errors,
        "avg_ms": statistics.mean(latencies),
        "p95_ms": sorted_latencies[p95_index],
        "max_ms": max(latencies),
    }
    if extra:
        summary.update(extra)
    return summary


def run_chatbot_dialogue_load(iterations: int) -> dict:
    latencies: list[float] = []
    errors = 0

    with patch.object(orchestrator.user_agent, "invoke", return_value=None):
        with patch.object(orchestrator.user_agent, "get_state") as mock_get_state:
            snapshot = type(
                "Snapshot",
                (),
                {"values": {"messages": [AIMessage(content="Skyline assistant response")]}}
            )
            mock_get_state.return_value = snapshot

            for i in range(iterations):
                started = time.perf_counter()
                try:
                    cfg = {"configurable": {"thread_id": f"chatbot-load-{i % 10}"}}
                    orchestrator.master_orchestrator.invoke(
                        {"messages": [HumanMessage(content="What are the parking hours?")]},
                        config=cfg,
                    )
                except Exception:
                    errors += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000.0)

    return _summarize("chatbot_dialogue", latencies, errors)


def run_admin_confirmation_load(iterations: int) -> dict:
    backup = {key: asdict(value) for key, value in fake_db_instance.items()}
    latencies: list[float] = []
    errors = 0

    try:
        with patch("admin_tools.debug_print_fake_db", return_value=None):
            for i in range(iterations):
                reservation_id = f"admin-load-{i}"
                fake_db_instance[reservation_id] = ReservationData(
                    full_name="Admin Load User",
                    numplate=f"BG-ADM-{i:04d}",
                    datetime_start=dt(2026, 4, 20, 10, 0),
                    datetime_end=dt(2026, 4, 20, 12, 0),
                    status="pending",
                    escalated_to_admin=True,
                    escalated_at=dt.now(),
                )

                started = time.perf_counter()
                try:
                    # Reject path exercises admin confirmation logic without MCP call.
                    apply_reservation_decision(
                        reservation_id=reservation_id,
                        status="rejected",
                        note="load-test rejection",
                    )
                except Exception:
                    errors += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000.0)
    finally:
        fake_db_instance.clear()
        for rid, record in backup.items():
            fake_db_instance[rid] = ReservationData(**record)

    return _summarize("admin_confirmation", latencies, errors)


def run_mcp_recording_load(iterations: int) -> dict:
    backup = {key: asdict(value) for key, value in fake_db_instance.items()}
    latencies: list[float] = []
    errors = 0
    save_calls = 0

    def _fake_save(_payload):
        return "ok"

    try:
        with patch("admin_tools.debug_print_fake_db", return_value=None):
            with patch("admin_tools.save_reservation_via_mcp", side_effect=_fake_save) as mocked_save:
                for i in range(iterations):
                    reservation_id = f"mcp-load-{i}"
                    fake_db_instance[reservation_id] = ReservationData(
                        full_name="MCP Load User",
                        numplate=f"BG-MCP-{i:04d}",
                        datetime_start=dt(2026, 4, 20, 10, 0),
                        datetime_end=dt(2026, 4, 20, 12, 0),
                        status="pending",
                        escalated_to_admin=True,
                        escalated_at=dt.now(),
                    )

                    started = time.perf_counter()
                    try:
                        # Approve path triggers MCP save boundary.
                        apply_reservation_decision(
                            reservation_id=reservation_id,
                            status="approved",
                            note="load-test approval",
                        )
                    except Exception:
                        errors += 1
                    finally:
                        latencies.append((time.perf_counter() - started) * 1000.0)

                save_calls = mocked_save.call_count
    finally:
        fake_db_instance.clear()
        for rid, record in backup.items():
            fake_db_instance[rid] = ReservationData(**record)

    return _summarize("mcp_recording", latencies, errors, {"mcp_save_calls": save_calls})


def _print_report(results: list[dict]) -> None:
    print("Load check report")
    print("Scenarios: chatbot_dialogue, admin_confirmation, mcp_recording")
    print("")
    for result in results:
        print(f"[{result['scenario']}]")
        print(f"Iterations: {result['iterations']}")
        print(f"Errors: {result['errors']}")
        print(f"Average latency (ms): {result['avg_ms']:.4f}")
        print(f"P95 latency (ms): {result['p95_ms']:.4f}")
        print(f"Max latency (ms): {result['max_ms']:.4f}")
        if "mcp_save_calls" in result:
            print(f"MCP save calls: {result['mcp_save_calls']}")
        print("")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run load checks")
    parser.add_argument("--iterations", type=int, default=300)
    args = parser.parse_args()

    results = [
        run_chatbot_dialogue_load(args.iterations),
        run_admin_confirmation_load(args.iterations),
        run_mcp_recording_load(args.iterations),
    ]
    _print_report(results)


if __name__ == "__main__":
    main()
