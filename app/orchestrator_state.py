from __future__ import annotations

from typing import Any, TypedDict


class AgentOSState(TypedDict):
    project_id: str
    session_id: str
    trace_id: str
    prompt: str
    attachments: list[dict[str, str]]
    tasks: list[dict[str, Any]]
    current_task_index: int
    agent_sequence: list[str]
    results: dict[str, Any]
    errors: list[dict[str, Any]]
    pending_hitl: list[str]
    status: str
    circuit_breaker: dict[str, int]
    start_time: float
    parallel_batch: list[str]


MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 3
TASK_PRIORITY_DEFAULT = 0
