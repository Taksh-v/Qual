"""
intelligence/admin_logger.py
----------------------------
Singleton logger for tracking agentic traces, latency, and system health.
Used by the Admin Dashboard to visualize the "Full Flow" of the system.
"""

import json
import logging
import os
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class AdminLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AdminLogger, cls).__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        # Buffer for the last 50 queries (each query has multiple events)
        self.trace_history = deque(maxlen=50)
        self.current_traces: Dict[str, List[Dict[str, Any]]] = {}
        self.audit_file = "logs/audit.jsonl"
        os.makedirs("logs", exist_ok=True)
        
        # System health metrics
        self.metrics = {
            "total_queries": 0,
            "failed_queries": 0,
            "p50_latency_ms": 0,
            "p99_latency_ms": 0,
            "agent_performance": {}, # agent_name -> {avg_latency, error_count}
            "last_ingestion": {}     # source -> timestamp
        }

    def start_trace(self, question: str) -> str:
        """Initialize a new query trace. Returns a trace ID."""
        trace_id = f"tr_{int(time.time() * 1000)}"
        self.current_traces[trace_id] = []
        self.metrics["total_queries"] += 1
        return trace_id

    def log_event(self, trace_id: str, stage: str, data: Dict[str, Any], agent_name: str = "", iteration: int = 0, elapsed_ms: int = 0):
        """Append an event to an active trace."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "stage": stage,
            "agent_name": agent_name,
            "iteration": iteration,
            "elapsed_ms": elapsed_ms,
            "data": data
        }
        if trace_id in self.current_traces:
            self.current_traces[trace_id].append(event)
        
        # Monitor for errors
        if stage == "error" or (data and "error" in str(data).lower()):
            self._log_audit(trace_id, stage, agent_name, str(data))

    def end_trace(self, trace_id: str, final_data: Dict[str, Any]):
        """Finalize a trace and move it to history."""
        if trace_id in self.current_traces:
            trace = {
                "trace_id": trace_id,
                "question": final_data.get("question", "Unknown"),
                "events": self.current_traces[trace_id],
                "summary": {
                    "total_ms": final_data.get("elapsed_ms", 0),
                    "steps": len(self.current_traces[trace_id]),
                    "status": "COMPLETED" if "error" not in final_data else "FAILED"
                }
            }
            if trace["summary"]["status"] == "FAILED":
                self.metrics["failed_queries"] += 1
                
            self.trace_history.appendleft(trace)
            del self.current_traces[trace_id]
            
            # Update metrics (simplified p50 logic for singleton)
            # In a real system, we'd use a more sophisticated rolling window
            self._update_metrics(trace["summary"]["total_ms"])

    def _update_metrics(self, last_latency: int):
        # Naive rolling average for p50
        prev_p50 = self.metrics["p50_latency_ms"]
        if prev_p50 == 0:
            self.metrics["p50_latency_ms"] = last_latency
        else:
            self.metrics["p50_latency_ms"] = int((prev_p50 * 0.9) + (last_latency * 0.1))

    def _log_audit(self, trace_id: str, stage: str, agent: str, error: str):
        try:
            with open(self.audit_file, "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.utcnow().isoformat(),
                    "trace_id": trace_id,
                    "stage": stage,
                    "agent": agent,
                    "error": error
                }) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.trace_history)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics,
            "active_traces": len(self.current_traces),
            "history_count": len(self.trace_history)
        }

# Global singleton instance
admin_logger = AdminLogger()
