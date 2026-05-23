"""Kanban board backend with WebSocket updates."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.utils.logging import get_broadcaster, get_logger

logger = get_logger("kanban")

COLUMNS = ["backlog", "todo", "in_progress", "to_review", "done", "archived"]


class KanbanCard:
    def __init__(
        self,
        title: str,
        description: str = "",
        column: str = "backlog",
        task_id: str = "",
        agent: str = "",
        session_id: str = "",
    ):
        self.id = str(uuid.uuid4())[:8]
        self.title = title
        self.description = description
        self.column = column if column in COLUMNS else "backlog"
        self.task_id = task_id
        self.agent = agent
        self.session_id = session_id
        self.created_at = datetime.now(UTC).isoformat()
        self.updated_at = self.created_at
        self.labels: list[str] = []
        self.assignee: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "column": self.column,
            "task_id": self.task_id,
            "agent": self.agent,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "labels": self.labels,
            "assignee": self.assignee,
        }


class KanbanBoard:
    def __init__(self, project_id: str = "default"):
        self.project_id = project_id
        self.cards: dict[str, KanbanCard] = {}
        self.logger = get_logger(f"kanban_{project_id}")
        self.broadcaster = get_broadcaster()

    def add_card(
        self,
        title: str,
        description: str = "",
        column: str = "backlog",
        task_id: str = "",
        agent: str = "",
        session_id: str = "",
    ) -> KanbanCard:
        card = KanbanCard(title, description, column, task_id, agent, session_id)
        self.cards[card.id] = card
        self.logger.log_action(
            "kanban",
            "card_added",
            "completed",
            details={"card_id": card.id, "title": title, "column": column},
        )
        return card

    def move_card(self, card_id: str, new_column: str) -> bool:
        if card_id not in self.cards or new_column not in COLUMNS:
            return False
        self.cards[card_id].column = new_column
        self.cards[card_id].updated_at = datetime.now(UTC).isoformat()

        return True

    def delete_card(self, card_id: str) -> bool:
        if card_id in self.cards:
            del self.cards[card_id]
            self.logger.log_action(
                "kanban", "card_deleted", "completed", details={"card_id": card_id}
            )
            return True
        return False

    def get_column(self, column: str) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.cards.values() if c.column == column]

    def get_all(self) -> dict[str, list[dict[str, Any]]]:
        return {col: self.get_column(col) for col in COLUMNS}

    def update_card(self, card_id: str, **kwargs: Any) -> bool:
        if card_id not in self.cards:
            return False
        card = self.cards[card_id]
        for k, v in kwargs.items():
            if hasattr(card, k) and k != "id":
                setattr(card, k, v)
        card.updated_at = datetime.now(UTC).isoformat()
        return True


_kanban_boards: dict[str, KanbanBoard] = {}


def get_kanban_board(project_id: str = "default") -> KanbanBoard:
    if project_id not in _kanban_boards:
        _kanban_boards[project_id] = KanbanBoard(project_id)
    return _kanban_boards[project_id]
