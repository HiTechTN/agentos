"""Pulse — real-time visual dashboard data."""

from datetime import datetime, timezone
from typing import Any

from app.utils.logging import get_logger

logger = get_logger("pulse")


class PulseMetric:
    def __init__(self, name: str, value: float, unit: str = ""):
        self.name = name
        self.value = value
        self.unit = unit
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "unit": self.unit, "timestamp": self.timestamp}


class PulseSnapshot:
    def __init__(self):
        self.metrics: list[PulseMetric] = []
        self.active_agents: int = 0
        self.tasks_completed: int = 0
        self.tasks_in_progress: int = 0
        self.tasks_review: int = 0
        self.cards_by_column: dict[str, int] = {}
        self.agent_activity: dict[str, str] = {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def add_metric(self, name: str, value: float, unit: str = ""):
        self.metrics.append(PulseMetric(name, value, unit))

    def to_dict(self) -> dict:
        return {
            "metrics": [m.to_dict() for m in self.metrics],
            "active_agents": self.active_agents,
            "tasks_completed": self.tasks_completed,
            "tasks_in_progress": self.tasks_in_progress,
            "tasks_review": self.tasks_review,
            "cards_by_column": self.cards_by_column,
            "agent_activity": self.agent_activity,
            "timestamp": self.timestamp,
        }


class PulseEngine:
    def __init__(self):
        self.logger = get_logger("pulse_engine")
        self.history: list[PulseSnapshot] = []

    async def snapshot(self, kanban_data: dict[str, list] | None = None,
                       agent_statuses: dict[str, str] | None = None) -> PulseSnapshot:
        snap = PulseSnapshot()
        if kanban_data:
            snap.cards_by_column = {col: len(cards) for col, cards in kanban_data.items()}
            snap.tasks_in_progress = len(kanban_data.get("in_progress", []))
            snap.tasks_review = len(kanban_data.get("to_review", []))
            snap.tasks_completed = len(kanban_data.get("done", []))
        if agent_statuses:
            snap.agent_activity = agent_statuses
            snap.active_agents = sum(1 for s in agent_statuses.values() if s == "running")
        self.history.append(snap)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        return snap

    def get_timeline(self, limit: int = 60) -> list[dict]:
        return [s.to_dict() for s in self.history[-limit:]]


_pulse_engine: PulseEngine | None = None


def get_pulse() -> PulseEngine:
    global _pulse_engine
    if _pulse_engine is None:
        _pulse_engine = PulseEngine()
    return _pulse_engine
