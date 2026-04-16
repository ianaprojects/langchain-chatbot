import unittest
from datetime import datetime as dt
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

import orchestrator
from fake_db import ReservationData, fake_db_instance


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self._backup = dict(fake_db_instance)

    def tearDown(self):
        fake_db_instance.clear()
        fake_db_instance.update(self._backup)

    def test_should_escalate_to_admin_true_for_pending(self):
        fake_db_instance["user-1"] = ReservationData(
            full_name="Test User",
            numplate="BG-001-AA",
            datetime_start=dt(2026, 4, 20, 10, 0),
            datetime_end=dt(2026, 4, 20, 12, 0),
            status="pending",
            escalated_to_admin=True,
        )

        self.assertTrue(orchestrator.should_escalate_to_admin("user-1"))

    def test_should_escalate_to_admin_false_for_non_pending(self):
        fake_db_instance["user-2"] = ReservationData(
            full_name="Test User",
            numplate="BG-002-BB",
            datetime_start=dt(2026, 4, 20, 10, 0),
            datetime_end=dt(2026, 4, 20, 12, 0),
            status="approved",
            escalated_to_admin=True,
        )

        self.assertFalse(orchestrator.should_escalate_to_admin("user-2"))

    def test_run_user_interaction_node_uses_user_agent_output(self):
        state = {"messages": [HumanMessage(content="I need parking")]} 
        config = {"configurable": {"thread_id": "user-3"}}

        snapshot = type("Snapshot", (), {"values": {"messages": [AIMessage(content="Pending request created")]}})

        with patch.object(orchestrator.user_agent, "invoke", return_value=None) as invoke_mock:
            with patch.object(orchestrator.user_agent, "get_state", return_value=snapshot):
                result = orchestrator.run_user_interaction_node(state, config)

        invoke_mock.assert_called_once()
        self.assertIn("messages", result)
        self.assertEqual(result["messages"][0].content, "Pending request created")

    def test_admin_review_node_adds_user_notification(self):
        state = {"messages": [HumanMessage(content="book")], "escalate_to_admin": True}
        config = {"configurable": {"thread_id": "user-4"}}

        with patch("orchestrator.invoke_admin_agent", return_value={"messages": []}) as invoke_admin_mock:
            with patch("orchestrator.get_result_text", return_value="Pending reservations listed"):
                result = orchestrator.admin_review_node(state, config)

        invoke_admin_mock.assert_called_once()
        self.assertIn("admin_summary", result)
        self.assertIn("messages", result)
        self.assertIn("escalated", result["messages"][0].content.lower())

    def test_master_orchestrator_compiles(self):
        graph = orchestrator.create_master_orchestrator()
        self.assertIsNotNone(graph)

    def test_orchestrator_full_flow_no_escalation(self):
        """Test complete orchestration path when no escalation is needed (info query)."""
        config = {"configurable": {"thread_id": "info-user"}}
        
        # No pending reservation -> no escalation needed
        initial_state = {"messages": [HumanMessage(content="What are your hours?")]}
        
        with patch.object(orchestrator.user_agent, "invoke", return_value=None):
            with patch.object(orchestrator.user_agent, "get_state") as mock_get_state:
                mock_snapshot = type("Snapshot", (), {
                    "values": {"messages": [AIMessage(content="We're open 24/7")]}
                })
                mock_get_state.return_value = mock_snapshot
                
                result = orchestrator.master_orchestrator.invoke(initial_state, config=config)
        
        # Should complete without admin review
        self.assertIn("messages", result)
        self.assertEqual(result["messages"][-1].content, "We're open 24/7")

    def test_orchestrator_full_flow_with_escalation(self):
        """Test complete orchestration path when escalation is triggered (pending reservation)."""
        thread_id = "booking-user"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Create a pending reservation that triggers escalation
        fake_db_instance[thread_id] = ReservationData(
            full_name="Booking User",
            numplate="BG-BOOK-1",
            datetime_start=dt(2026, 4, 20, 10, 0),
            datetime_end=dt(2026, 4, 20, 12, 0),
            status="pending",
            escalated_to_admin=True,
        )
        
        initial_state = {"messages": [HumanMessage(content="book a spot")]}
        
        with patch.object(orchestrator.user_agent, "invoke", return_value=None):
            with patch.object(orchestrator.user_agent, "get_state") as mock_user_state:
                mock_user_snapshot = type("Snapshot", (), {
                    "values": {"messages": [AIMessage(content="Request created")]}
                })
                mock_user_state.return_value = mock_user_snapshot
                
                with patch("orchestrator.invoke_admin_agent") as mock_admin:
                    with patch("orchestrator.get_result_text", return_value="Pending review"):
                        result = orchestrator.master_orchestrator.invoke(initial_state, config=config)
        
        # Should reach admin stage
        mock_admin.assert_called_once()
        self.assertIn("messages", result)
        # Last message should be escalation notification
        final_msg = result["messages"][-1].content
        self.assertIn("escalated", final_msg.lower())

    def test_orchestrator_state_isolation_between_threads(self):
        """Verify orchestrator maintains separate state for different thread IDs."""
        user1_config = {"configurable": {"thread_id": "user-1"}}
        user2_config = {"configurable": {"thread_id": "user-2"}}
        
        # Only user-1 has a pending reservation
        fake_db_instance["user-1"] = ReservationData(
            full_name="User One",
            numplate="BG-001-U1",
            datetime_start=dt(2026, 4, 20, 10, 0),
            datetime_end=dt(2026, 4, 20, 12, 0),
            status="pending",
            escalated_to_admin=True,
        )
        
        with patch.object(orchestrator.user_agent, "invoke", return_value=None):
            with patch.object(orchestrator.user_agent, "get_state") as mock_state:
                mock_snapshot = type("Snapshot", (), {
                    "values": {"messages": [AIMessage(content="Response")]}
                })
                mock_state.return_value = mock_snapshot
                
                with patch("orchestrator.invoke_admin_agent") as mock_admin:
                    with patch("orchestrator.get_result_text", return_value="Admin view"):
                        # Invoke user-1: should escalate
                        result1 = orchestrator.master_orchestrator.invoke(
                            {"messages": [HumanMessage(content="book")]},
                            config=user1_config
                        )
                        escalation_call_count_after_user1 = mock_admin.call_count
                        
                        # Invoke user-2: should NOT escalate
                        result2 = orchestrator.master_orchestrator.invoke(
                            {"messages": [HumanMessage(content="info")]},
                            config=user2_config
                        )
                        escalation_call_count_after_user2 = mock_admin.call_count
        
        # Admin should be called only once (for user-1)
        self.assertEqual(escalation_call_count_after_user1, 1)
        self.assertEqual(escalation_call_count_after_user2, 1)


if __name__ == "__main__":
    unittest.main()
