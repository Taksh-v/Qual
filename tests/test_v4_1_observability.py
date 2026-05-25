"""
tests/test_v4_1_observability.py
--------------------------------
Integration test for Admin Observability & Stabilization (V4.1).
Verifies that AdminLogger captures traces and app.py exposes the dashboard.
"""

import asyncio
import json
import os
import sys
import unittest
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from intelligence.admin_logger import admin_logger
from intelligence.agentic_rag.orchestrator import AgenticOrchestrator

class TestV41Observability(unittest.IsolatedAsyncioTestCase):

    async def test_01_trace_capture(self):
        """Verify that a full orchestrator run creates a valid trace in AdminLogger."""
        orchestrator = AgenticOrchestrator(max_iterations=1)
        question = "How is the war affecting Lebanese gold prices?"
        
        # Run a simulated pipeline
        events = []
        async for event in orchestrator.run_async(question):
            events.append(event)
            
        history = admin_logger.get_history()
        self.assertGreater(len(history), 0, "Trace history should not be empty")
        
        latest = history[0]
        self.assertEqual(latest["question"], question)
        self.assertGreater(len(latest["events"]), 5, "Trace should contain multiple flow events")
        
        # Verify stages are logged
        stages = [e["stage"] for e in latest["events"]]
        self.assertIn("planning", stages)
        self.assertIn("agent_brief", stages)
        self.assertIn("final", stages)
        
        print(f"PASS: Captured trace with {len(latest['events'])} events.")

    def test_02_metrics_summary(self):
        """Verify the health summary logic."""
        summary = admin_logger.get_summary()
        self.assertIn("metrics", summary)
        self.assertGreater(summary["metrics"]["total_queries"], 0)
        print(f"PASS: Summary metrics: {summary['metrics']}")

if __name__ == "__main__":
    unittest.main()
